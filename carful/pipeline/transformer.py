"""
CARFul - Transformation Pipeline

Chains processing stages: read → coerce types → map enums → validate → persist

This module provides a flexible, composable pipeline architecture for
transforming raw CSV transaction data into CARF-compliant records.

Pipeline Stages:
1. READ: Ingest CSV with chunked reading
2. COERCE: Convert data types (Decimal, datetime)
3. MAP: Apply CARF transaction code mapping
4. VALIDATE: Check business rules and constraints
5. PERSIST: Store to SQLite database

Each stage is implemented as a PipelineStage that can be composed
and executed in sequence.
"""

import pandas as pd
from decimal import Decimal
from datetime import datetime
from typing import Optional, Callable, Any, Generator, Protocol
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
from pathlib import Path
import sqlite3
import logging
import time

# Local imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from transformers.numeric import NumericTransformer, NumericResult
from transformers.dates import DateTransformer, DateResult, ReportingPeriodValidator
from transaction_mapper import map_transaction, MappingResult, MappingConfidence
from ingestion.csv_reader import CSVReader, ColumnMapper
from ingestion.chunk_processor import ChunkProcessor, ProcessedChunk

logger = logging.getLogger(__name__)


class StageStatus(Enum):
    """Status of a pipeline stage execution."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class StageResult:
    """Result from executing a pipeline stage."""
    stage_name: str
    status: StageStatus
    rows_in: int
    rows_out: int
    errors: list[dict] = field(default_factory=list)
    warnings: list[dict] = field(default_factory=list)
    processing_time_ms: float = 0.0
    metadata: dict = field(default_factory=dict)

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.rows_in == 0:
            return 100.0
        return (self.rows_out / self.rows_in) * 100

    @property
    def error_count(self) -> int:
        """Get total error count."""
        return len(self.errors)


@dataclass
class ErrorRecord:
    """Record of a transformation error."""
    stage: str
    row_number: int
    field: str
    original_value: Any
    error_message: str
    severity: str = "error"  # error, warning, info
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            'stage': self.stage,
            'row': self.row_number,
            'field': self.field,
            'original': str(self.original_value),
            'error': self.error_message,
            'severity': self.severity,
            'timestamp': self.timestamp.isoformat(),
        }


class ErrorReport:
    """
    Collects and reports transformation errors across pipeline stages.

    Tracks row numbers, fields, and error messages for user feedback.
    Provides summary statistics and exportable error reports.
    """

    def __init__(self, max_errors: int = 1000):
        """
        Initialize error report.

        Args:
            max_errors: Maximum errors to retain (oldest dropped)
        """
        self.max_errors = max_errors
        self.errors: list[ErrorRecord] = []
        self.warnings: list[ErrorRecord] = []
        self._error_counts: dict[str, int] = {}
        self._warning_counts: dict[str, int] = {}

    def add_error(
        self,
        stage: str,
        row_number: int,
        field: str,
        original_value: Any,
        error_message: str,
    ) -> None:
        """Add an error record."""
        self._error_counts[stage] = self._error_counts.get(stage, 0) + 1

        if len(self.errors) < self.max_errors:
            self.errors.append(ErrorRecord(
                stage=stage,
                row_number=row_number,
                field=field,
                original_value=original_value,
                error_message=error_message,
                severity="error",
            ))

    def add_warning(
        self,
        stage: str,
        row_number: int,
        field: str,
        original_value: Any,
        warning_message: str,
    ) -> None:
        """Add a warning record."""
        self._warning_counts[stage] = self._warning_counts.get(stage, 0) + 1

        if len(self.warnings) < self.max_errors:
            self.warnings.append(ErrorRecord(
                stage=stage,
                row_number=row_number,
                field=field,
                original_value=original_value,
                error_message=warning_message,
                severity="warning",
            ))

    @property
    def total_errors(self) -> int:
        """Get total error count across all stages."""
        return sum(self._error_counts.values())

    @property
    def total_warnings(self) -> int:
        """Get total warning count across all stages."""
        return sum(self._warning_counts.values())

    def get_errors_by_stage(self, stage: str) -> list[ErrorRecord]:
        """Get errors for a specific stage."""
        return [e for e in self.errors if e.stage == stage]

    def get_errors_by_row(self, row_number: int) -> list[ErrorRecord]:
        """Get all errors for a specific row."""
        return [e for e in self.errors if e.row_number == row_number]

    def get_summary(self) -> dict:
        """Get summary statistics."""
        return {
            'total_errors': self.total_errors,
            'total_warnings': self.total_warnings,
            'errors_by_stage': dict(self._error_counts),
            'warnings_by_stage': dict(self._warning_counts),
            'sample_errors': [e.to_dict() for e in self.errors[:10]],
        }

    def to_dataframe(self) -> pd.DataFrame:
        """Convert errors to DataFrame for export."""
        records = [e.to_dict() for e in self.errors + self.warnings]
        return pd.DataFrame(records)

    def export_csv(self, path: str) -> None:
        """Export errors to CSV file."""
        df = self.to_dataframe()
        df.to_csv(path, index=False)


class PipelineStage(ABC):
    """Abstract base class for pipeline stages."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Stage name for logging and error tracking."""
        pass

    @abstractmethod
    def process(
        self,
        df: pd.DataFrame,
        error_report: ErrorReport,
    ) -> tuple[pd.DataFrame, StageResult]:
        """
        Process a DataFrame chunk.

        Args:
            df: Input DataFrame
            error_report: Error collection

        Returns:
            Tuple of (processed DataFrame, stage result)
        """
        pass


class CoerceTypesStage(PipelineStage):
    """
    Coerces data types to XSD-compliant formats.

    Handles:
    - Numeric fields → Decimal (20 decimal precision)
    - Date fields → datetime (ISO 8601)
    - String fields → stripped, normalized
    """

    name = "coerce_types"

    def __init__(
        self,
        amount_fields: list[str] = None,
        date_fields: list[str] = None,
        reporting_year: Optional[int] = None,
    ):
        """
        Initialize coercion stage.

        Args:
            amount_fields: Fields to coerce to Decimal
            date_fields: Fields to coerce to datetime
            reporting_year: Optional year for date validation
        """
        self.amount_fields = amount_fields or ['amount', 'fiat_value', 'fee']
        self.date_fields = date_fields or ['timestamp']
        self.numeric_transformer = NumericTransformer(max_precision=20)
        self.date_transformer = DateTransformer()
        self.period_validator = (
            ReportingPeriodValidator(reporting_year) if reporting_year else None
        )

    def process(
        self,
        df: pd.DataFrame,
        error_report: ErrorReport,
    ) -> tuple[pd.DataFrame, StageResult]:
        """Process DataFrame through type coercion."""
        start_time = time.time()
        rows_in = len(df)
        df = df.copy()
        errors = []
        warnings = []

        # Coerce numeric fields
        for field in self.amount_fields:
            if field not in df.columns:
                continue

            for idx, row in df.iterrows():
                result = self.numeric_transformer.transform(row[field])
                if result.success:
                    df.at[idx, field] = result.value
                else:
                    error_report.add_error(
                        stage=self.name,
                        row_number=row.get('_source_row', idx),
                        field=field,
                        original_value=row[field],
                        error_message=result.error,
                    )
                    errors.append({
                        'row': row.get('_source_row', idx),
                        'field': field,
                        'error': result.error,
                    })

        # Coerce date fields
        for field in self.date_fields:
            if field not in df.columns:
                continue

            for idx, row in df.iterrows():
                result = self.date_transformer.transform(row[field])
                if result.success:
                    df.at[idx, field] = result.value

                    # Validate reporting period if configured
                    if self.period_validator and not self.period_validator.is_valid(result.value):
                        error_report.add_warning(
                            stage=self.name,
                            row_number=row.get('_source_row', idx),
                            field=field,
                            original_value=row[field],
                            warning_message=f"Date outside reporting year {self.period_validator.reporting_year}",
                        )
                        warnings.append({
                            'row': row.get('_source_row', idx),
                            'field': field,
                            'warning': 'Outside reporting period',
                        })
                else:
                    error_report.add_error(
                        stage=self.name,
                        row_number=row.get('_source_row', idx),
                        field=field,
                        original_value=row[field],
                        error_message=result.error,
                    )
                    errors.append({
                        'row': row.get('_source_row', idx),
                        'field': field,
                        'error': result.error,
                    })

        processing_time = (time.time() - start_time) * 1000

        return df, StageResult(
            stage_name=self.name,
            status=StageStatus.COMPLETED,
            rows_in=rows_in,
            rows_out=len(df),
            errors=errors,
            warnings=warnings,
            processing_time_ms=processing_time,
        )


class MapEnumsStage(PipelineStage):
    """
    Maps transaction descriptions to CARF enumeration codes.

    Uses keyword heuristics to classify transactions.
    """

    name = "map_enums"

    def __init__(
        self,
        description_field: str = 'description',
        amount_field: str = 'amount',
        min_confidence: MappingConfidence = MappingConfidence.MEDIUM,
    ):
        """
        Initialize mapping stage.

        Args:
            description_field: Field containing transaction descriptions
            amount_field: Field for determining transaction direction
            min_confidence: Minimum confidence level to accept mapping
        """
        self.description_field = description_field
        self.amount_field = amount_field
        self.min_confidence = min_confidence

    def process(
        self,
        df: pd.DataFrame,
        error_report: ErrorReport,
    ) -> tuple[pd.DataFrame, StageResult]:
        """Process DataFrame through enum mapping."""
        start_time = time.time()
        rows_in = len(df)
        df = df.copy()
        errors = []
        warnings = []

        # Add mapping columns
        df['_carf_code'] = None
        df['_carf_category'] = None
        df['_carf_confidence'] = None
        df['_carf_suggested'] = False

        if self.description_field not in df.columns:
            return df, StageResult(
                stage_name=self.name,
                status=StageStatus.SKIPPED,
                rows_in=rows_in,
                rows_out=len(df),
                metadata={'reason': f"Field '{self.description_field}' not found"},
            )

        for idx, row in df.iterrows():
            description = str(row.get(self.description_field, ''))
            amount = None

            if self.amount_field in df.columns:
                try:
                    amount = float(row[self.amount_field])
                except (ValueError, TypeError):
                    pass

            result = map_transaction(description, amount)

            df.at[idx, '_carf_code'] = result.transaction_type
            df.at[idx, '_carf_category'] = result.category.value if hasattr(result.category, 'value') else result.category
            df.at[idx, '_carf_confidence'] = result.confidence.value
            df.at[idx, '_carf_suggested'] = result.suggested

            # Track low confidence mappings
            if result.confidence.value < self.min_confidence.value:
                error_report.add_warning(
                    stage=self.name,
                    row_number=row.get('_source_row', idx),
                    field=self.description_field,
                    original_value=description,
                    warning_message=f"Low confidence mapping: {result.confidence.value}",
                )
                warnings.append({
                    'row': row.get('_source_row', idx),
                    'confidence': result.confidence.value,
                })

        processing_time = (time.time() - start_time) * 1000

        return df, StageResult(
            stage_name=self.name,
            status=StageStatus.COMPLETED,
            rows_in=rows_in,
            rows_out=len(df),
            errors=errors,
            warnings=warnings,
            processing_time_ms=processing_time,
        )


class ValidateStage(PipelineStage):
    """
    Validates data against business rules and constraints.

    Checks:
    - Required fields are present
    - Values are within acceptable ranges
    - Cross-field consistency
    """

    name = "validate"

    def __init__(
        self,
        required_fields: list[str] = None,
        max_amount: Optional[Decimal] = None,
        min_amount: Optional[Decimal] = None,
    ):
        """
        Initialize validation stage.

        Args:
            required_fields: Fields that must have non-null values
            max_amount: Maximum allowed amount
            min_amount: Minimum allowed amount
        """
        self.required_fields = required_fields or ['timestamp', 'amount', 'asset']
        self.max_amount = max_amount
        self.min_amount = min_amount

    def process(
        self,
        df: pd.DataFrame,
        error_report: ErrorReport,
    ) -> tuple[pd.DataFrame, StageResult]:
        """Process DataFrame through validation."""
        start_time = time.time()
        rows_in = len(df)
        df = df.copy()
        errors = []
        valid_mask = pd.Series([True] * len(df), index=df.index)

        # Check required fields
        for field in self.required_fields:
            if field not in df.columns:
                continue

            null_mask = df[field].isna()
            for idx in df[null_mask].index:
                row = df.loc[idx]
                error_report.add_error(
                    stage=self.name,
                    row_number=row.get('_source_row', idx),
                    field=field,
                    original_value=None,
                    error_message=f"Required field '{field}' is missing",
                )
                errors.append({
                    'row': row.get('_source_row', idx),
                    'field': field,
                    'error': 'Missing required field',
                })
                valid_mask[idx] = False

        # Check amount bounds
        if 'amount' in df.columns:
            for idx, row in df.iterrows():
                amount = row['amount']
                if not isinstance(amount, Decimal):
                    continue

                if self.max_amount and abs(amount) > self.max_amount:
                    error_report.add_warning(
                        stage=self.name,
                        row_number=row.get('_source_row', idx),
                        field='amount',
                        original_value=amount,
                        warning_message=f"Amount exceeds maximum: {amount}",
                    )

                if self.min_amount and abs(amount) < self.min_amount:
                    error_report.add_warning(
                        stage=self.name,
                        row_number=row.get('_source_row', idx),
                        field='amount',
                        original_value=amount,
                        warning_message=f"Amount below minimum: {amount}",
                    )

        # Add validation status column
        df['_valid'] = valid_mask

        processing_time = (time.time() - start_time) * 1000

        return df, StageResult(
            stage_name=self.name,
            status=StageStatus.COMPLETED,
            rows_in=rows_in,
            rows_out=valid_mask.sum(),
            errors=errors,
            processing_time_ms=processing_time,
            metadata={'valid_rows': int(valid_mask.sum())},
        )


class PersistStage(PipelineStage):
    """
    Persists validated data to SQLite database.
    """

    name = "persist"

    def __init__(
        self,
        db_path: str,
        table_name: str = 'transaction',
        batch_size: int = 1000,
    ):
        """
        Initialize persistence stage.

        Args:
            db_path: Path to SQLite database
            table_name: Target table name
            batch_size: Rows per INSERT batch
        """
        self.db_path = db_path
        self.table_name = table_name
        self.batch_size = batch_size

    def process(
        self,
        df: pd.DataFrame,
        error_report: ErrorReport,
    ) -> tuple[pd.DataFrame, StageResult]:
        """Process DataFrame through persistence."""
        start_time = time.time()
        rows_in = len(df)

        # Filter to valid rows only
        if '_valid' in df.columns:
            df = df[df['_valid'] == True].copy()

        if len(df) == 0:
            return df, StageResult(
                stage_name=self.name,
                status=StageStatus.SKIPPED,
                rows_in=rows_in,
                rows_out=0,
                metadata={'reason': 'No valid rows to persist'},
            )

        # Prepare columns for database
        db_columns = [c for c in df.columns if not c.startswith('_')]

        try:
            with sqlite3.connect(self.db_path) as conn:
                df[db_columns].to_sql(
                    self.table_name,
                    conn,
                    if_exists='append',
                    index=False,
                )
                rows_persisted = len(df)

        except Exception as e:
            return df, StageResult(
                stage_name=self.name,
                status=StageStatus.FAILED,
                rows_in=rows_in,
                rows_out=0,
                errors=[{'error': str(e)}],
            )

        processing_time = (time.time() - start_time) * 1000

        return df, StageResult(
            stage_name=self.name,
            status=StageStatus.COMPLETED,
            rows_in=rows_in,
            rows_out=rows_persisted,
            processing_time_ms=processing_time,
        )


@dataclass
class PipelineResult:
    """Result from running the full pipeline."""
    success: bool
    total_rows_in: int
    total_rows_out: int
    stage_results: list[StageResult]
    error_report: ErrorReport
    total_time_ms: float

    @property
    def summary(self) -> dict:
        """Get pipeline execution summary."""
        return {
            'success': self.success,
            'rows_in': self.total_rows_in,
            'rows_out': self.total_rows_out,
            'stages': len(self.stage_results),
            'total_errors': self.error_report.total_errors,
            'total_warnings': self.error_report.total_warnings,
            'time_ms': self.total_time_ms,
            'rows_per_second': (
                self.total_rows_in / (self.total_time_ms / 1000)
                if self.total_time_ms > 0 else 0
            ),
        }


class TransformationPipeline:
    """
    Orchestrates the complete transformation pipeline.

    Chains stages: read → coerce → map → validate → persist

    Example usage:
        pipeline = TransformationPipeline()
        pipeline.add_stage(CoerceTypesStage())
        pipeline.add_stage(MapEnumsStage())
        pipeline.add_stage(ValidateStage())

        result = pipeline.run("transactions.csv")
    """

    def __init__(self):
        """Initialize empty pipeline."""
        self.stages: list[PipelineStage] = []
        self.error_report = ErrorReport()

    def add_stage(self, stage: PipelineStage) -> 'TransformationPipeline':
        """
        Add a stage to the pipeline.

        Args:
            stage: Pipeline stage to add

        Returns:
            Self for chaining
        """
        self.stages.append(stage)
        return self

    def run(
        self,
        input_data: pd.DataFrame,
    ) -> PipelineResult:
        """
        Run the pipeline on input data.

        Args:
            input_data: Input DataFrame

        Returns:
            PipelineResult with all stage results
        """
        start_time = time.time()
        self.error_report = ErrorReport()  # Reset

        current_df = input_data.copy()
        stage_results = []
        rows_in = len(current_df)

        for stage in self.stages:
            try:
                current_df, result = stage.process(current_df, self.error_report)
                stage_results.append(result)

                if result.status == StageStatus.FAILED:
                    logger.error(f"Stage {stage.name} failed")
                    break

            except Exception as e:
                logger.exception(f"Stage {stage.name} raised exception")
                stage_results.append(StageResult(
                    stage_name=stage.name,
                    status=StageStatus.FAILED,
                    rows_in=len(current_df),
                    rows_out=0,
                    errors=[{'error': str(e)}],
                ))
                break

        total_time = (time.time() - start_time) * 1000

        # Determine overall success
        success = all(
            r.status in [StageStatus.COMPLETED, StageStatus.SKIPPED]
            for r in stage_results
        )

        return PipelineResult(
            success=success,
            total_rows_in=rows_in,
            total_rows_out=len(current_df) if success else 0,
            stage_results=stage_results,
            error_report=self.error_report,
            total_time_ms=total_time,
        )

    def run_chunked(
        self,
        file_path: str,
        chunk_size: int = 5000,
        preset: Optional[str] = None,
    ) -> Generator[PipelineResult, None, dict]:
        """
        Run pipeline on a file with chunked processing.

        Args:
            file_path: Path to CSV file
            chunk_size: Rows per chunk
            preset: Column mapping preset

        Yields:
            PipelineResult for each chunk

        Returns:
            Aggregate statistics
        """
        mapper = ColumnMapper.from_preset(preset) if preset else None
        reader = CSVReader(chunk_size=chunk_size, column_mapper=mapper)

        total_rows = 0
        total_errors = 0
        total_time = 0

        gen = reader.read_chunks(file_path)

        try:
            while True:
                chunk_df, metadata = next(gen)

                result = self.run(chunk_df)
                yield result

                total_rows += result.total_rows_in
                total_errors += result.error_report.total_errors
                total_time += result.total_time_ms

        except StopIteration:
            pass

        return {
            'total_rows': total_rows,
            'total_errors': total_errors,
            'total_time_ms': total_time,
            'rows_per_second': total_rows / (total_time / 1000) if total_time > 0 else 0,
        }


def create_default_pipeline(
    reporting_year: int = 2025,
    db_path: Optional[str] = None,
) -> TransformationPipeline:
    """
    Create a pipeline with default stages.

    Args:
        reporting_year: Year for date validation
        db_path: Optional database path for persistence

    Returns:
        Configured TransformationPipeline
    """
    pipeline = TransformationPipeline()

    # Add standard stages
    pipeline.add_stage(CoerceTypesStage(reporting_year=reporting_year))
    pipeline.add_stage(MapEnumsStage())
    pipeline.add_stage(ValidateStage())

    # Add persistence if db_path provided
    if db_path:
        pipeline.add_stage(PersistStage(db_path=db_path))

    return pipeline


if __name__ == "__main__":
    print("CARFul Transformation Pipeline")
    print("=" * 50)
    print("\nPipeline stages: read → coerce → map → validate → persist")
    print("\nUsage:")
    print("  pipeline = create_default_pipeline(reporting_year=2025)")
    print("  result = pipeline.run(df)")
    print("  print(result.summary)")
