"""
CARFul - Chunk Processor with Generator Protocol

This module provides generator-based chunk processing for pipeline integration.
Implements the iterator protocol for seamless integration with downstream consumers.

Features:
- Generator protocol for memory-efficient streaming
- Transaction mapping integration
- Batch statistics collection
- Progress tracking callbacks
"""

import pandas as pd
from typing import Generator, Optional, Callable, Any, Iterator
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import sys

# Add parent for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from ingestion.csv_reader import CSVReader, ColumnMapper, ChunkMetadata, ReadResult
from transaction_mapper import map_transaction, MappingResult, get_mapping_statistics


@dataclass
class ProcessedChunk:
    """A fully processed chunk ready for persistence."""
    chunk_number: int
    data: pd.DataFrame
    row_count: int
    start_row: int
    end_row: int
    mapping_results: list[MappingResult]
    processing_time_ms: float
    errors: list[dict] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        """Calculate success rate (non-error rows)."""
        if self.row_count == 0:
            return 0.0
        return (self.row_count - len(self.errors)) / self.row_count * 100


@dataclass
class ProcessingStats:
    """Aggregated statistics from processing."""
    total_rows: int = 0
    total_chunks: int = 0
    total_errors: int = 0
    total_time_ms: float = 0.0
    mapping_stats: dict = field(default_factory=dict)
    rows_per_second: float = 0.0

    def update(self, chunk: ProcessedChunk) -> None:
        """Update stats with chunk data."""
        self.total_rows += chunk.row_count
        self.total_chunks += 1
        self.total_errors += len(chunk.errors)
        self.total_time_ms += chunk.processing_time_ms

        if self.total_time_ms > 0:
            self.rows_per_second = self.total_rows / (self.total_time_ms / 1000)


class ChunkProcessor:
    """
    Generator-based chunk processor for streaming CSV processing.

    Implements iterator protocol for use in for-loops and pipeline stages.
    """

    def __init__(
        self,
        reader: Optional[CSVReader] = None,
        apply_transaction_mapping: bool = True,
        description_field: str = 'description',
        amount_field: Optional[str] = 'amount',
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ):
        """
        Initialize chunk processor.

        Args:
            reader: CSVReader instance
            apply_transaction_mapping: Whether to apply CARF code mapping
            description_field: Field containing transaction descriptions
            amount_field: Field containing amounts (for direction detection)
            progress_callback: Callback(rows_processed, chunk_number)
        """
        self.reader = reader or CSVReader()
        self.apply_transaction_mapping = apply_transaction_mapping
        self.description_field = description_field
        self.amount_field = amount_field
        self.progress_callback = progress_callback
        self.stats = ProcessingStats()

    def process_file(
        self,
        file_path: str,
        **read_kwargs
    ) -> Generator[ProcessedChunk, None, ProcessingStats]:
        """
        Process a CSV file, yielding processed chunks.

        This generator yields ProcessedChunk objects and returns
        final ProcessingStats when exhausted.

        Args:
            file_path: Path to CSV file
            **read_kwargs: Additional arguments for CSV reader

        Yields:
            ProcessedChunk objects

        Returns:
            ProcessingStats when generator is exhausted
        """
        self.stats = ProcessingStats()  # Reset stats

        gen = self.reader.read_chunks(file_path, **read_kwargs)

        try:
            while True:
                start_time = datetime.now()
                chunk_df, metadata = next(gen)

                # Apply transaction mapping if enabled
                mapping_results = []
                if self.apply_transaction_mapping:
                    mapping_results = self._apply_mapping(chunk_df)
                    # Add mapping columns to DataFrame
                    chunk_df = self._add_mapping_columns(chunk_df, mapping_results)

                processing_time = (datetime.now() - start_time).total_seconds() * 1000

                processed = ProcessedChunk(
                    chunk_number=metadata.chunk_number,
                    data=chunk_df,
                    row_count=metadata.rows_in_chunk,
                    start_row=metadata.start_row,
                    end_row=metadata.end_row,
                    mapping_results=mapping_results,
                    processing_time_ms=processing_time + metadata.processing_time_ms,
                    errors=metadata.errors,
                )

                self.stats.update(processed)

                # Progress callback
                if self.progress_callback:
                    self.progress_callback(self.stats.total_rows, metadata.chunk_number)

                yield processed

        except StopIteration as e:
            # Capture final read result
            read_result: ReadResult = e.value
            if read_result:
                self.stats.total_time_ms = read_result.processing_time_ms

        # Calculate final mapping stats
        if self.apply_transaction_mapping:
            self.stats.mapping_stats = self._calculate_mapping_stats()

        return self.stats

    def _apply_mapping(self, df: pd.DataFrame) -> list[MappingResult]:
        """Apply transaction mapping to each row."""
        results = []

        desc_col = self.description_field
        amt_col = self.amount_field

        for idx, row in df.iterrows():
            description = str(row.get(desc_col, '')) if desc_col in df.columns else ''
            amount = None
            if amt_col and amt_col in df.columns:
                try:
                    amount = float(row[amt_col])
                except (ValueError, TypeError):
                    pass

            result = map_transaction(description, amount)
            results.append(result)

        return results

    def _add_mapping_columns(
        self,
        df: pd.DataFrame,
        results: list[MappingResult]
    ) -> pd.DataFrame:
        """Add mapping result columns to DataFrame."""
        df = df.copy()

        df['_carf_code'] = [r.transaction_type for r in results]
        df['_carf_category'] = [r.category.value if hasattr(r.category, 'value') else r.category for r in results]
        df['_carf_confidence'] = [r.confidence.value for r in results]
        df['_carf_suggested'] = [r.suggested for r in results]

        return df

    def _calculate_mapping_stats(self) -> dict:
        """Calculate aggregate mapping statistics."""
        # This would aggregate from all chunks - simplified here
        return {
            'total_mapped': self.stats.total_rows,
            'mapping_applied': True,
        }

    def __iter__(self) -> Iterator[ProcessedChunk]:
        """Make processor iterable (requires file_path to be set)."""
        raise NotImplementedError(
            "Use process_file() to get a generator. "
            "ChunkProcessor itself is not directly iterable."
        )


class StreamingProcessor:
    """
    Streaming processor for very large files.

    Provides utilities for processing files that don't fit in memory.
    """

    def __init__(self, chunk_size: int = 5000):
        self.chunk_size = chunk_size
        self.processor = ChunkProcessor(
            reader=CSVReader(chunk_size=chunk_size)
        )

    def stream_to_database(
        self,
        file_path: str,
        db_writer: Callable[[pd.DataFrame], int],
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> ProcessingStats:
        """
        Stream CSV data directly to database.

        Args:
            file_path: Path to CSV file
            db_writer: Callable that writes DataFrame to DB, returns rows written
            progress_callback: Progress callback(rows, chunks)

        Returns:
            ProcessingStats
        """
        self.processor.progress_callback = progress_callback
        rows_written = 0

        gen = self.processor.process_file(file_path)
        stats = None

        try:
            for chunk in gen:
                written = db_writer(chunk.data)
                rows_written += written
        except StopIteration as e:
            stats = e.value

        return stats or self.processor.stats

    def stream_with_transform(
        self,
        file_path: str,
        transform: Callable[[pd.DataFrame], pd.DataFrame],
        output_path: Optional[str] = None,
    ) -> ProcessingStats:
        """
        Stream CSV with transformation applied to each chunk.

        Args:
            file_path: Input CSV path
            transform: Transform function
            output_path: Optional output CSV path

        Returns:
            ProcessingStats
        """
        first_chunk = True
        gen = self.processor.process_file(file_path)

        try:
            for chunk in gen:
                transformed = transform(chunk.data)

                if output_path:
                    mode = 'w' if first_chunk else 'a'
                    header = first_chunk
                    transformed.to_csv(output_path, mode=mode, header=header, index=False)
                    first_chunk = False

        except StopIteration as e:
            return e.value

        return self.processor.stats


def create_chunk_generator(
    file_path: str,
    chunk_size: int = 5000,
    apply_mapping: bool = True,
    preset: Optional[str] = None,
) -> Generator[ProcessedChunk, None, ProcessingStats]:
    """
    Convenience function to create a chunk generator.

    Args:
        file_path: Path to CSV file
        chunk_size: Rows per chunk
        apply_mapping: Apply CARF transaction mapping
        preset: Column mapping preset name

    Yields:
        ProcessedChunk objects

    Returns:
        ProcessingStats
    """
    # Set up column mapper
    mapper = None
    if preset:
        mapper = ColumnMapper.from_preset(preset)

    reader = CSVReader(chunk_size=chunk_size, column_mapper=mapper)
    processor = ChunkProcessor(reader=reader, apply_transaction_mapping=apply_mapping)

    return processor.process_file(file_path)


if __name__ == "__main__":
    print("CARFul Chunk Processor")
    print("=" * 50)
    print("Generator-based streaming processor for large CSV files.")
    print("\nUsage:")
    print("  gen = create_chunk_generator('transactions.csv')")
    print("  for chunk in gen:")
    print("      process(chunk.data)")
    print("  stats = gen.value  # After exhaustion")
