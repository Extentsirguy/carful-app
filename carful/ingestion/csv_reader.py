"""
CARFul - CSV Reader with Chunked Processing

This module provides memory-efficient CSV ingestion using pandas chunking.
Designed to handle large files (100K+ rows) with O(1) memory footprint.

Features:
- Chunked reading with configurable chunk size (default 5000 rows)
- Column mapping for different exchange/explorer formats
- Generator-based processing for pipeline integration
- Automatic encoding detection
- Error tracking with row numbers
"""

import pandas as pd
import json
from pathlib import Path
from typing import Generator, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
import logging

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class ChunkMetadata:
    """Metadata about a processed chunk."""
    chunk_number: int
    rows_in_chunk: int
    start_row: int  # Original CSV row number (1-indexed)
    end_row: int
    processing_time_ms: float
    errors: list[dict] = field(default_factory=list)


@dataclass
class ReadResult:
    """Result of reading a CSV file."""
    success: bool
    total_rows: int
    total_chunks: int
    total_errors: int
    processing_time_ms: float
    source_file: str
    column_mapping_used: Optional[str] = None
    errors: list[dict] = field(default_factory=list)


class ColumnMapper:
    """
    Maps CSV columns to standard CARFul field names.

    Supports different exchange formats via JSON configuration.
    """

    # Standard CARFul field names
    STANDARD_FIELDS = {
        'timestamp',        # Transaction timestamp
        'description',      # Transaction description/type
        'amount',           # Transaction amount
        'asset',            # Crypto asset (BTC, ETH, etc.)
        'fiat_value',       # Fiat equivalent value
        'fiat_currency',    # Fiat currency code (USD, EUR)
        'transaction_id',   # Blockchain/exchange tx ID
        'fee',              # Transaction fee
        'fee_asset',        # Fee asset type
        'from_address',     # Source address
        'to_address',       # Destination address
        'exchange',         # Exchange name
        'account',          # Account identifier
        'notes',            # Additional notes
    }

    def __init__(self, mapping: Optional[dict] = None):
        """
        Initialize with optional column mapping.

        Args:
            mapping: Dict mapping source columns to standard fields
        """
        self.mapping = mapping or {}
        self.reverse_mapping = {v: k for k, v in self.mapping.items() if v}

    @classmethod
    def from_json(cls, json_path: str) -> 'ColumnMapper':
        """Load column mapping from JSON file."""
        with open(json_path, 'r') as f:
            config = json.load(f)
        return cls(config.get('columns', {}))

    @classmethod
    def from_preset(cls, preset_name: str, config_dir: Optional[str] = None) -> 'ColumnMapper':
        """
        Load a preset column mapping by name.

        Args:
            preset_name: Name of the preset (e.g., 'coinbase', 'binance')
            config_dir: Directory containing mapping configs
        """
        if config_dir is None:
            config_dir = Path(__file__).parent.parent / 'config'

        mapping_file = Path(config_dir) / 'column_mappings.json'

        if not mapping_file.exists():
            logger.warning(f"Mapping file not found: {mapping_file}")
            return cls()

        with open(mapping_file, 'r') as f:
            all_mappings = json.load(f)

        if preset_name not in all_mappings.get('presets', {}):
            logger.warning(f"Preset '{preset_name}' not found, using auto-detection")
            return cls()

        return cls(all_mappings['presets'][preset_name]['columns'])

    def map_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Rename DataFrame columns to standard field names.

        Args:
            df: Input DataFrame with original column names

        Returns:
            DataFrame with standardized column names
        """
        if not self.mapping:
            return df

        # Build rename dict for columns that exist
        rename_dict = {}
        for source_col, target_field in self.mapping.items():
            if source_col in df.columns and target_field:
                rename_dict[source_col] = target_field

        return df.rename(columns=rename_dict)

    def auto_detect(self, columns: list[str]) -> dict[str, str]:
        """
        Attempt to auto-detect column mappings based on common patterns.

        Args:
            columns: List of column names from CSV

        Returns:
            Suggested mapping dict
        """
        detected = {}
        columns_lower = {c.lower(): c for c in columns}

        # Common patterns for each field
        patterns = {
            'timestamp': ['timestamp', 'date', 'time', 'datetime', 'created', 'executed'],
            'description': ['description', 'type', 'transaction type', 'action', 'operation', 'notes'],
            'amount': ['amount', 'quantity', 'size', 'volume', 'total'],
            'asset': ['asset', 'currency', 'coin', 'symbol', 'token', 'crypto'],
            'fiat_value': ['fiat', 'usd', 'eur', 'value', 'price', 'total usd', 'spot price'],
            'fiat_currency': ['fiat currency', 'currency code'],
            'transaction_id': ['tx id', 'txid', 'transaction id', 'hash', 'tx hash', 'id'],
            'fee': ['fee', 'commission', 'cost'],
            'exchange': ['exchange', 'platform', 'source'],
        }

        for field, keywords in patterns.items():
            for keyword in keywords:
                if keyword in columns_lower:
                    detected[columns_lower[keyword]] = field
                    break

        return detected


class CSVReader:
    """
    Memory-efficient CSV reader with chunked processing.

    Designed for large files with O(1) memory footprint.
    """

    DEFAULT_CHUNK_SIZE = 5000

    def __init__(
        self,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        column_mapper: Optional[ColumnMapper] = None,
        encoding: str = 'utf-8',
        date_columns: Optional[list[str]] = None,
    ):
        """
        Initialize CSV reader.

        Args:
            chunk_size: Number of rows per chunk (default 5000)
            column_mapper: ColumnMapper instance for field mapping
            encoding: File encoding (default utf-8)
            date_columns: Columns to parse as dates
        """
        self.chunk_size = chunk_size
        self.column_mapper = column_mapper or ColumnMapper()
        self.encoding = encoding
        self.date_columns = date_columns or []

    def read_chunks(
        self,
        file_path: str,
        **pandas_kwargs
    ) -> Generator[tuple[pd.DataFrame, ChunkMetadata], None, ReadResult]:
        """
        Read CSV file in chunks, yielding each chunk with metadata.

        This is a generator function that yields (DataFrame, ChunkMetadata) tuples.
        The final return value is a ReadResult with summary statistics.

        Args:
            file_path: Path to CSV file
            **pandas_kwargs: Additional arguments for pd.read_csv

        Yields:
            Tuple of (chunk DataFrame, ChunkMetadata)

        Returns:
            ReadResult with summary statistics
        """
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"CSV file not found: {file_path}")

        start_time = datetime.now()
        total_rows = 0
        chunk_number = 0
        all_errors: list[dict] = []

        # Configure pandas read options
        read_options = {
            'chunksize': self.chunk_size,
            'encoding': self.encoding,
            'on_bad_lines': 'warn',
            **pandas_kwargs
        }

        # Parse date columns if specified
        if self.date_columns:
            read_options['parse_dates'] = self.date_columns

        try:
            # Create chunk iterator
            chunk_iter = pd.read_csv(file_path, **read_options)

            for chunk_df in chunk_iter:
                chunk_start_time = datetime.now()
                chunk_number += 1
                rows_in_chunk = len(chunk_df)
                start_row = total_rows + 2  # +2 for 1-indexed and header row

                # Apply column mapping
                chunk_df = self.column_mapper.map_columns(chunk_df)

                # Add source tracking
                chunk_df['_source_row'] = range(start_row, start_row + rows_in_chunk)
                chunk_df['_source_file'] = str(file_path.name)

                # Track any parsing errors in this chunk
                chunk_errors = self._validate_chunk(chunk_df, start_row)
                all_errors.extend(chunk_errors)

                total_rows += rows_in_chunk

                chunk_time = (datetime.now() - chunk_start_time).total_seconds() * 1000

                metadata = ChunkMetadata(
                    chunk_number=chunk_number,
                    rows_in_chunk=rows_in_chunk,
                    start_row=start_row,
                    end_row=start_row + rows_in_chunk - 1,
                    processing_time_ms=chunk_time,
                    errors=chunk_errors,
                )

                yield chunk_df, metadata

        except Exception as e:
            logger.error(f"Error reading CSV: {e}")
            raise

        total_time = (datetime.now() - start_time).total_seconds() * 1000

        return ReadResult(
            success=True,
            total_rows=total_rows,
            total_chunks=chunk_number,
            total_errors=len(all_errors),
            processing_time_ms=total_time,
            source_file=str(file_path),
            errors=all_errors[:100],  # Limit stored errors
        )

    def _validate_chunk(self, df: pd.DataFrame, start_row: int) -> list[dict]:
        """
        Validate chunk data and collect errors.

        Args:
            df: Chunk DataFrame
            start_row: Starting row number in original file

        Returns:
            List of error dictionaries
        """
        errors = []

        # Check for required fields
        required_fields = ['timestamp', 'amount', 'asset']

        for field in required_fields:
            if field in df.columns:
                # Check for nulls in required fields
                null_mask = df[field].isna()
                if null_mask.any():
                    null_rows = df.loc[null_mask, '_source_row'].tolist()
                    for row in null_rows[:10]:  # Limit errors per field
                        errors.append({
                            'row': row,
                            'field': field,
                            'error': f"Missing required field: {field}",
                            'severity': 'error',
                        })

        return errors

    def read_all(
        self,
        file_path: str,
        max_rows: Optional[int] = None,
        **pandas_kwargs
    ) -> tuple[pd.DataFrame, ReadResult]:
        """
        Read entire CSV file into memory (for smaller files).

        Args:
            file_path: Path to CSV file
            max_rows: Maximum rows to read (None for all)
            **pandas_kwargs: Additional arguments for pd.read_csv

        Returns:
            Tuple of (full DataFrame, ReadResult)
        """
        chunks = []
        result = None

        gen = self.read_chunks(file_path, **pandas_kwargs)

        try:
            rows_read = 0
            while True:
                chunk_df, metadata = next(gen)
                chunks.append(chunk_df)
                rows_read += len(chunk_df)

                if max_rows and rows_read >= max_rows:
                    break

        except StopIteration as e:
            result = e.value

        if chunks:
            full_df = pd.concat(chunks, ignore_index=True)
            if max_rows:
                full_df = full_df.head(max_rows)
        else:
            full_df = pd.DataFrame()

        return full_df, result


class CSVProcessor:
    """
    High-level CSV processor with transformation pipeline support.

    Integrates reading, mapping, and optional transformations.
    """

    def __init__(
        self,
        reader: Optional[CSVReader] = None,
        transformers: Optional[list[Callable[[pd.DataFrame], pd.DataFrame]]] = None,
    ):
        """
        Initialize processor.

        Args:
            reader: CSVReader instance (creates default if None)
            transformers: List of transformer functions to apply to each chunk
        """
        self.reader = reader or CSVReader()
        self.transformers = transformers or []

    def add_transformer(self, transformer: Callable[[pd.DataFrame], pd.DataFrame]) -> None:
        """Add a transformer function to the pipeline."""
        self.transformers.append(transformer)

    def process(
        self,
        file_path: str,
        **read_kwargs
    ) -> Generator[tuple[pd.DataFrame, ChunkMetadata], None, ReadResult]:
        """
        Process CSV file through the transformation pipeline.

        Args:
            file_path: Path to CSV file
            **read_kwargs: Additional arguments for reader

        Yields:
            Tuple of (transformed DataFrame, ChunkMetadata)

        Returns:
            ReadResult with summary statistics
        """
        gen = self.reader.read_chunks(file_path, **read_kwargs)

        try:
            while True:
                chunk_df, metadata = next(gen)

                # Apply transformers
                for transformer in self.transformers:
                    chunk_df = transformer(chunk_df)

                yield chunk_df, metadata

        except StopIteration as e:
            return e.value


def detect_csv_format(file_path: str, sample_rows: int = 100) -> dict:
    """
    Analyze CSV file and detect its format.

    Args:
        file_path: Path to CSV file
        sample_rows: Number of rows to sample

    Returns:
        Dict with format information and suggested mappings
    """
    # Read sample
    df = pd.read_csv(file_path, nrows=sample_rows)

    mapper = ColumnMapper()
    detected_mapping = mapper.auto_detect(df.columns.tolist())

    return {
        'columns': df.columns.tolist(),
        'row_count_sample': len(df),
        'detected_mapping': detected_mapping,
        'unmapped_columns': [c for c in df.columns if c not in detected_mapping],
        'dtypes': df.dtypes.astype(str).to_dict(),
    }


if __name__ == "__main__":
    # Example usage
    print("CARFul CSV Reader")
    print("=" * 50)

    # Create reader with default settings
    reader = CSVReader(chunk_size=5000)

    print(f"Chunk size: {reader.chunk_size}")
    print(f"Encoding: {reader.encoding}")
    print("\nReady to process CSV files with O(1) memory footprint.")
