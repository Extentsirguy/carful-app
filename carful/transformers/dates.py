"""
CARFul - Date/Time Transformer

Converts various input date formats to XSD-compliant ISO 8601:
- Dates: YYYY-MM-DD
- DateTimes: YYYY-MM-DDTHH:mm:ss (with optional timezone)

Handles common exchange export formats:
- US: MM/DD/YYYY, MM-DD-YYYY
- European: DD/MM/YYYY, DD.MM.YYYY
- ISO: YYYY-MM-DD, YYYY/MM/DD
- Unix timestamps (seconds and milliseconds)
- Various timestamp formats with/without timezone
"""

from datetime import datetime, date, timezone, timedelta
from typing import Optional, Union, Any
from dataclasses import dataclass, field
from enum import Enum
import re
import logging

logger = logging.getLogger(__name__)


class DateFormat(Enum):
    """Standard date output formats."""
    DATE = "YYYY-MM-DD"
    DATETIME = "YYYY-MM-DDTHH:mm:ss"
    DATETIME_TZ = "YYYY-MM-DDTHH:mm:ssZ"


class DateParseError(Exception):
    """Raised when date parsing fails."""
    pass


@dataclass
class DateResult:
    """Result of date transformation."""
    success: bool
    value: Optional[datetime]
    original: Any
    error: Optional[str] = None
    format_detected: Optional[str] = None

    @property
    def as_date_string(self) -> str:
        """Return as YYYY-MM-DD string."""
        if self.value is None:
            return ""
        return self.value.strftime('%Y-%m-%d')

    @property
    def as_datetime_string(self) -> str:
        """Return as YYYY-MM-DDTHH:mm:ss string."""
        if self.value is None:
            return ""
        return self.value.strftime('%Y-%m-%dT%H:%M:%S')

    @property
    def as_datetime_utc_string(self) -> str:
        """Return as YYYY-MM-DDTHH:mm:ssZ string (UTC)."""
        if self.value is None:
            return ""
        # Convert to UTC if timezone aware
        if self.value.tzinfo is not None:
            utc_value = self.value.astimezone(timezone.utc)
        else:
            utc_value = self.value
        return utc_value.strftime('%Y-%m-%dT%H:%M:%SZ')


@dataclass
class DateStats:
    """Statistics from date transformation batch."""
    total: int = 0
    successful: int = 0
    failed: int = 0
    errors: list[dict] = field(default_factory=list)
    earliest: Optional[datetime] = None
    latest: Optional[datetime] = None
    formats_detected: dict = field(default_factory=dict)

    def update(self, result: DateResult, row_number: Optional[int] = None) -> None:
        """Update stats with a transformation result."""
        self.total += 1

        if result.success and result.value is not None:
            self.successful += 1

            # Track date range
            if self.earliest is None or result.value < self.earliest:
                self.earliest = result.value
            if self.latest is None or result.value > self.latest:
                self.latest = result.value

            # Track formats
            if result.format_detected:
                self.formats_detected[result.format_detected] = \
                    self.formats_detected.get(result.format_detected, 0) + 1
        else:
            self.failed += 1
            if len(self.errors) < 100:  # Limit error tracking
                self.errors.append({
                    'row': row_number,
                    'original': str(result.original),
                    'error': result.error,
                })

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.total == 0:
            return 0.0
        return (self.successful / self.total) * 100

    @property
    def date_range_days(self) -> Optional[int]:
        """Calculate the date range in days."""
        if self.earliest and self.latest:
            return (self.latest - self.earliest).days
        return None


class DateTransformer:
    """
    Transforms various date/time inputs to XSD-compliant formats.

    Handles formats from major exchanges:
    - Coinbase: "2025-01-15T10:30:00Z"
    - Binance: "2025-01-15 10:30:00"
    - Kraken: Unix timestamp
    - Block explorers: Various formats
    """

    # Common date patterns with their strptime formats
    # Order matters: more specific patterns first
    DATE_PATTERNS = [
        # ISO 8601 variants (most common in APIs)
        (r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z?$', '%Y-%m-%dT%H:%M:%S.%f', 'ISO datetime with ms'),
        (r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$', '%Y-%m-%dT%H:%M:%SZ', 'ISO datetime UTC'),
        (r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$', '%Y-%m-%dT%H:%M:%S', 'ISO datetime'),
        (r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$', '%Y-%m-%d %H:%M:%S', 'ISO datetime space'),
        (r'^\d{4}-\d{2}-\d{2}$', '%Y-%m-%d', 'ISO date'),

        # US formats
        (r'^\d{1,2}/\d{1,2}/\d{4} \d{1,2}:\d{2}:\d{2} [AP]M$', '%m/%d/%Y %I:%M:%S %p', 'US datetime 12h'),
        (r'^\d{1,2}/\d{1,2}/\d{4} \d{1,2}:\d{2}:\d{2}$', '%m/%d/%Y %H:%M:%S', 'US datetime'),
        (r'^\d{1,2}/\d{1,2}/\d{4} \d{1,2}:\d{2}$', '%m/%d/%Y %H:%M', 'US datetime short'),
        (r'^\d{1,2}/\d{1,2}/\d{4}$', '%m/%d/%Y', 'US date'),
        (r'^\d{1,2}-\d{1,2}-\d{4}$', '%m-%d-%Y', 'US date dash'),

        # European formats
        (r'^\d{1,2}\.\d{1,2}\.\d{4} \d{1,2}:\d{2}:\d{2}$', '%d.%m.%Y %H:%M:%S', 'EU datetime'),
        (r'^\d{1,2}\.\d{1,2}\.\d{4}$', '%d.%m.%Y', 'EU date'),
        (r'^\d{1,2}/\d{1,2}/\d{4}$', '%d/%m/%Y', 'EU date slash'),  # Ambiguous, tried after US

        # Other common formats
        (r'^\d{4}/\d{2}/\d{2}$', '%Y/%m/%d', 'Asian date'),
        (r'^\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}$', '%Y/%m/%d %H:%M:%S', 'Asian datetime'),

        # Month name formats
        (r'^[A-Za-z]{3} \d{1,2}, \d{4}$', '%b %d, %Y', 'Month name short'),
        (r'^[A-Za-z]+ \d{1,2}, \d{4}$', '%B %d, %Y', 'Month name long'),

        # Compact formats
        (r'^\d{8}$', '%Y%m%d', 'Compact date'),
        (r'^\d{14}$', '%Y%m%d%H%M%S', 'Compact datetime'),
    ]

    # Timezone offset pattern
    TZ_OFFSET_PATTERN = re.compile(r'([+-])(\d{2}):?(\d{2})$')

    # Unix timestamp bounds (roughly 1970-2100)
    UNIX_MIN = 0
    UNIX_MAX = 4102444800  # 2100-01-01
    UNIX_MS_MIN = UNIX_MIN * 1000
    UNIX_MS_MAX = UNIX_MAX * 1000

    def __init__(
        self,
        output_format: DateFormat = DateFormat.DATETIME,
        assume_utc: bool = True,
        year_cutoff: int = 2030,
    ):
        """
        Initialize date transformer.

        Args:
            output_format: Desired output format
            assume_utc: Assume UTC for timezone-naive inputs
            year_cutoff: For 2-digit years, values > cutoff assumed 1900s
        """
        self.output_format = output_format
        self.assume_utc = assume_utc
        self.year_cutoff = year_cutoff

        # Compile patterns
        self._compiled_patterns = [
            (re.compile(pattern), fmt, name)
            for pattern, fmt, name in self.DATE_PATTERNS
        ]

    def transform(self, value: Any) -> DateResult:
        """
        Transform a single value to datetime.

        Args:
            value: Input value (string, datetime, date, int/float for timestamp)

        Returns:
            DateResult with success status and transformed value
        """
        original = value

        # Handle None/empty
        if value is None:
            return DateResult(
                success=False,
                value=None,
                original=original,
                error="Value is None"
            )

        # Handle datetime objects
        if isinstance(value, datetime):
            return DateResult(
                success=True,
                value=value,
                original=original,
                format_detected="datetime object"
            )

        # Handle date objects
        if isinstance(value, date):
            dt = datetime.combine(value, datetime.min.time())
            return DateResult(
                success=True,
                value=dt,
                original=original,
                format_detected="date object"
            )

        # Convert to string
        str_value = str(value).strip()

        if not str_value:
            return DateResult(
                success=False,
                value=None,
                original=original,
                error="Empty value"
            )

        # Try Unix timestamp
        timestamp_result = self._try_unix_timestamp(str_value, original)
        if timestamp_result:
            return timestamp_result

        # Try pattern matching
        for pattern, fmt, name in self._compiled_patterns:
            if pattern.match(str_value):
                try:
                    # Handle timezone offset
                    clean_value, tz_info = self._extract_timezone(str_value)

                    # Parse datetime
                    dt = datetime.strptime(clean_value, fmt)

                    # Apply timezone
                    if tz_info:
                        dt = dt.replace(tzinfo=tz_info)
                    elif self.assume_utc:
                        dt = dt.replace(tzinfo=timezone.utc)

                    return DateResult(
                        success=True,
                        value=dt,
                        original=original,
                        format_detected=name
                    )
                except ValueError:
                    continue  # Try next pattern

        # Try flexible parsing with dateutil if patterns fail
        result = self._try_flexible_parse(str_value, original)
        if result:
            return result

        return DateResult(
            success=False,
            value=None,
            original=original,
            error=f"Unrecognized date format: {str_value}"
        )

    def _try_unix_timestamp(self, value: str, original: Any) -> Optional[DateResult]:
        """Try to parse as Unix timestamp."""
        try:
            # Check if it's a number
            if not re.match(r'^-?\d+\.?\d*$', value):
                return None

            num = float(value)

            # Determine if seconds or milliseconds
            if self.UNIX_MIN <= num <= self.UNIX_MAX:
                # Seconds
                dt = datetime.fromtimestamp(num, tz=timezone.utc)
                return DateResult(
                    success=True,
                    value=dt,
                    original=original,
                    format_detected="Unix timestamp (seconds)"
                )
            elif self.UNIX_MS_MIN <= num <= self.UNIX_MS_MAX:
                # Milliseconds
                dt = datetime.fromtimestamp(num / 1000, tz=timezone.utc)
                return DateResult(
                    success=True,
                    value=dt,
                    original=original,
                    format_detected="Unix timestamp (milliseconds)"
                )
        except (ValueError, OSError, OverflowError):
            pass
        return None

    def _extract_timezone(self, value: str) -> tuple[str, Optional[timezone]]:
        """Extract and parse timezone offset from string."""
        # Handle Z suffix
        if value.endswith('Z'):
            return value[:-1], timezone.utc

        # Handle offset like +00:00, -05:00
        match = self.TZ_OFFSET_PATTERN.search(value)
        if match:
            sign = 1 if match.group(1) == '+' else -1
            hours = int(match.group(2))
            minutes = int(match.group(3))
            offset = timedelta(hours=hours * sign, minutes=minutes * sign)
            clean_value = value[:match.start()]
            return clean_value, timezone(offset)

        return value, None

    def _try_flexible_parse(self, value: str, original: Any) -> Optional[DateResult]:
        """Try flexible parsing for edge cases."""
        try:
            # Try common variations
            variations = [
                value,
                value.replace('T', ' '),
                value.replace(' ', 'T'),
            ]

            for v in variations:
                # Strip microseconds for cleaner parsing
                v = re.sub(r'\.\d+', '', v)
                # Strip timezone info temporarily
                v = re.sub(r'[+-]\d{2}:?\d{2}$', '', v)
                v = v.rstrip('Z')

                # Try ISO-like format
                try:
                    dt = datetime.fromisoformat(v)
                    if self.assume_utc:
                        dt = dt.replace(tzinfo=timezone.utc)
                    return DateResult(
                        success=True,
                        value=dt,
                        original=original,
                        format_detected="Flexible ISO"
                    )
                except ValueError:
                    continue
        except Exception:
            pass
        return None

    def transform_batch(
        self,
        values: list[Any],
        start_row: int = 1,
    ) -> tuple[list[DateResult], DateStats]:
        """
        Transform a batch of values.

        Args:
            values: List of values to transform
            start_row: Starting row number for error tracking

        Returns:
            Tuple of (results list, aggregate stats)
        """
        results = []
        stats = DateStats()

        for i, value in enumerate(values):
            result = self.transform(value)
            results.append(result)
            stats.update(result, start_row + i)

        return results, stats

    def format_output(self, dt: datetime) -> str:
        """Format datetime according to output_format setting."""
        if dt is None:
            return ""

        if self.output_format == DateFormat.DATE:
            return dt.strftime('%Y-%m-%d')
        elif self.output_format == DateFormat.DATETIME:
            return dt.strftime('%Y-%m-%dT%H:%M:%S')
        elif self.output_format == DateFormat.DATETIME_TZ:
            if dt.tzinfo is not None:
                utc_dt = dt.astimezone(timezone.utc)
            else:
                utc_dt = dt
            return utc_dt.strftime('%Y-%m-%dT%H:%M:%SZ')
        return str(dt)


class ReportingPeriodValidator:
    """
    Validates dates fall within CARF reporting period.

    CARF reports are annual, covering a calendar year.
    """

    def __init__(self, reporting_year: int):
        """
        Initialize validator for a reporting year.

        Args:
            reporting_year: The calendar year being reported
        """
        self.reporting_year = reporting_year
        self.start_date = datetime(reporting_year, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        self.end_date = datetime(reporting_year, 12, 31, 23, 59, 59, tzinfo=timezone.utc)

    def is_valid(self, dt: datetime) -> bool:
        """Check if datetime falls within reporting period."""
        if dt is None:
            return False

        # Make timezone aware for comparison
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        return self.start_date <= dt <= self.end_date

    def validate_batch(
        self,
        dates: list[datetime],
    ) -> tuple[list[bool], int, int]:
        """
        Validate a batch of dates.

        Returns:
            Tuple of (validity list, valid count, invalid count)
        """
        results = []
        valid_count = 0
        invalid_count = 0

        for dt in dates:
            is_valid = self.is_valid(dt)
            results.append(is_valid)
            if is_valid:
                valid_count += 1
            else:
                invalid_count += 1

        return results, valid_count, invalid_count


def parse_date(value: Any, output_format: str = 'datetime') -> Optional[datetime]:
    """
    Convenience function to parse a single date.

    Args:
        value: Input value
        output_format: 'date', 'datetime', or 'datetime_tz'

    Returns:
        datetime value or None on failure
    """
    fmt = DateFormat.DATETIME
    if output_format == 'date':
        fmt = DateFormat.DATE
    elif output_format == 'datetime_tz':
        fmt = DateFormat.DATETIME_TZ

    transformer = DateTransformer(output_format=fmt)
    result = transformer.transform(value)
    return result.value if result.success else None


def format_xsd_date(dt: datetime) -> str:
    """Format datetime as XSD date (YYYY-MM-DD)."""
    if dt is None:
        return ""
    return dt.strftime('%Y-%m-%d')


def format_xsd_datetime(dt: datetime) -> str:
    """Format datetime as XSD dateTime (YYYY-MM-DDTHH:mm:ss)."""
    if dt is None:
        return ""
    return dt.strftime('%Y-%m-%dT%H:%M:%S')


if __name__ == "__main__":
    print("CARFul Date Transformer")
    print("=" * 50)

    transformer = DateTransformer()

    test_values = [
        "2025-01-15T10:30:00Z",         # ISO UTC
        "2025-01-15 10:30:00",          # ISO space
        "01/15/2025",                    # US date
        "15.01.2025",                    # EU date
        "1705312200",                    # Unix timestamp
        "1705312200000",                 # Unix ms
        "Jan 15, 2025",                  # Month name
        "2025/01/15 10:30:00",          # Asian format
        "01/15/2025 10:30:00 AM",       # US 12-hour
    ]

    print("\nTest transformations:")
    for val in test_values:
        result = transformer.transform(val)
        status = "✓" if result.success else "✗"
        output = result.as_datetime_string if result.success else result.error
        print(f"  {status} '{val}' → {output} ({result.format_detected})")
