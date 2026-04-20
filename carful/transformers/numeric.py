"""
CARFul - Numeric Transformer with Decimal Precision

Implements XSD-compliant numeric handling:
- Uses Decimal (not float) for all monetary amounts
- Supports up to 20 decimal places per CARF XSD requirements
- Handles various input formats (strings, floats, scientific notation)
- Provides rounding and precision control

CARF XSD Requirements:
- xs:decimal with up to 20 fractional digits
- Positive values for amounts, negative for fees in certain contexts
- Proper handling of zero values
"""

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, ROUND_DOWN, getcontext
from typing import Optional, Union, Any
from dataclasses import dataclass, field
from enum import Enum
import re
import logging

# Set high precision for Decimal operations
getcontext().prec = 28  # Enough for 20 decimal places + some headroom

logger = logging.getLogger(__name__)


class RoundingMode(Enum):
    """Rounding modes for Decimal operations."""
    HALF_UP = ROUND_HALF_UP      # Standard rounding (0.5 rounds up)
    DOWN = ROUND_DOWN            # Truncation (towards zero)


class NumericValidationError(Exception):
    """Raised when numeric validation fails."""
    pass


@dataclass
class NumericResult:
    """Result of numeric transformation."""
    success: bool
    value: Optional[Decimal]
    original: Any
    error: Optional[str] = None
    precision: int = 0

    @property
    def as_string(self) -> str:
        """Return value as XSD-compliant string."""
        if self.value is None:
            return ""
        # Remove trailing zeros but keep at least one decimal place
        normalized = self.value.normalize()
        return format(normalized, 'f')


@dataclass
class NumericStats:
    """Statistics from numeric transformation batch."""
    total: int = 0
    successful: int = 0
    failed: int = 0
    errors: list[dict] = field(default_factory=list)
    min_value: Optional[Decimal] = None
    max_value: Optional[Decimal] = None
    sum_value: Decimal = field(default_factory=lambda: Decimal('0'))

    def update(self, result: NumericResult, row_number: Optional[int] = None) -> None:
        """Update stats with a transformation result."""
        self.total += 1

        if result.success and result.value is not None:
            self.successful += 1

            # Update aggregates
            if self.min_value is None or result.value < self.min_value:
                self.min_value = result.value
            if self.max_value is None or result.value > self.max_value:
                self.max_value = result.value
            self.sum_value += result.value
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


class NumericTransformer:
    """
    Transforms various numeric inputs to XSD-compliant Decimals.

    Handles:
    - String numbers ("123.456", "1,234.56", "-0.00001")
    - Scientific notation ("1.5e-8", "2.3E+10")
    - Float/int values (converts to Decimal safely)
    - Currency symbols (strips $, €, £, etc.)
    - Thousands separators (commas, spaces)

    CARF XSD allows up to 20 decimal places for amounts.
    """

    # Maximum decimal places per XSD
    MAX_PRECISION = 20

    # Currency symbols to strip
    CURRENCY_SYMBOLS = re.compile(r'[$€£¥₿₹₽¢]')

    # Thousands separator patterns
    THOUSANDS_SEP = re.compile(r'[\s,]+(?=\d{3})')

    # Scientific notation
    SCIENTIFIC = re.compile(r'^-?\d+\.?\d*[eE][+-]?\d+$')

    def __init__(
        self,
        max_precision: int = MAX_PRECISION,
        rounding: RoundingMode = RoundingMode.HALF_UP,
        allow_negative: bool = True,
        strip_currency: bool = True,
    ):
        """
        Initialize numeric transformer.

        Args:
            max_precision: Maximum decimal places (default 20 per XSD)
            rounding: Rounding mode for excess precision
            allow_negative: Whether to allow negative values
            strip_currency: Whether to strip currency symbols
        """
        self.max_precision = min(max_precision, self.MAX_PRECISION)
        self.rounding = rounding.value
        self.allow_negative = allow_negative
        self.strip_currency = strip_currency

        # Quantize template for precision
        self._quantize = Decimal(10) ** -self.max_precision

    def transform(self, value: Any) -> NumericResult:
        """
        Transform a single value to Decimal.

        Args:
            value: Input value (string, float, int, Decimal)

        Returns:
            NumericResult with success status and transformed value
        """
        original = value

        # Handle None/empty
        if value is None:
            return NumericResult(
                success=False,
                value=None,
                original=original,
                error="Value is None"
            )

        # Convert to string for processing
        if isinstance(value, Decimal):
            str_value = str(value)
        elif isinstance(value, (int, float)):
            # Use string representation to avoid float precision issues
            str_value = repr(value) if isinstance(value, float) else str(value)
        else:
            str_value = str(value).strip()

        # Handle empty string
        if not str_value:
            return NumericResult(
                success=False,
                value=None,
                original=original,
                error="Empty value"
            )

        try:
            # Clean the string
            cleaned = self._clean_string(str_value)

            # Parse to Decimal
            decimal_value = Decimal(cleaned)

            # Check for negative values
            if not self.allow_negative and decimal_value < 0:
                return NumericResult(
                    success=False,
                    value=None,
                    original=original,
                    error="Negative values not allowed"
                )

            # Apply precision limit
            decimal_value = decimal_value.quantize(self._quantize, rounding=self.rounding)

            # Calculate actual precision used
            precision = self._get_precision(decimal_value)

            return NumericResult(
                success=True,
                value=decimal_value,
                original=original,
                precision=precision,
            )

        except InvalidOperation as e:
            return NumericResult(
                success=False,
                value=None,
                original=original,
                error=f"Invalid number format: {str(e)}"
            )
        except Exception as e:
            return NumericResult(
                success=False,
                value=None,
                original=original,
                error=f"Transformation error: {str(e)}"
            )

    def _clean_string(self, value: str) -> str:
        """Clean string for Decimal parsing."""
        result = value

        # Strip currency symbols
        if self.strip_currency:
            result = self.CURRENCY_SYMBOLS.sub('', result)

        # Handle parentheses as negative (accounting notation)
        if result.startswith('(') and result.endswith(')'):
            result = '-' + result[1:-1]

        # Remove thousands separators
        # Be careful with European format (1.234,56) vs US (1,234.56)
        if ',' in result and '.' in result:
            # Determine format based on position
            comma_pos = result.rfind(',')
            dot_pos = result.rfind('.')
            if comma_pos > dot_pos:
                # European format: 1.234,56 -> 1234.56
                result = result.replace('.', '').replace(',', '.')
            else:
                # US format: 1,234.56 -> 1234.56
                result = result.replace(',', '')
        elif ',' in result:
            # Could be European decimal or US thousands
            parts = result.split(',')
            if len(parts) == 2 and len(parts[1]) <= 3:
                # Likely European decimal: 123,45 -> 123.45
                result = result.replace(',', '.')
            else:
                # US thousands: 1,234,567 -> 1234567
                result = result.replace(',', '')

        # Remove whitespace (thousands separator)
        result = result.replace(' ', '').replace('\u00a0', '')

        # Handle plus sign
        result = result.lstrip('+')

        return result.strip()

    def _get_precision(self, value: Decimal) -> int:
        """Get the actual decimal precision of a value."""
        sign, digits, exponent = value.as_tuple()
        if exponent >= 0:
            return 0
        return abs(exponent)

    def transform_batch(
        self,
        values: list[Any],
        start_row: int = 1,
    ) -> tuple[list[NumericResult], NumericStats]:
        """
        Transform a batch of values.

        Args:
            values: List of values to transform
            start_row: Starting row number for error tracking

        Returns:
            Tuple of (results list, aggregate stats)
        """
        results = []
        stats = NumericStats()

        for i, value in enumerate(values):
            result = self.transform(value)
            results.append(result)
            stats.update(result, start_row + i)

        return results, stats


class CryptoAmountTransformer(NumericTransformer):
    """
    Specialized transformer for cryptocurrency amounts.

    Handles:
    - Satoshi notation (100000000 sats = 1 BTC)
    - Wei notation (1e18 wei = 1 ETH)
    - Common crypto precision requirements
    """

    # Satoshi/Wei conversion factors
    SATOSHI_FACTOR = Decimal('100000000')  # 1e8
    WEI_FACTOR = Decimal('1000000000000000000')  # 1e18

    def __init__(self, asset_type: Optional[str] = None, **kwargs):
        """
        Initialize crypto amount transformer.

        Args:
            asset_type: Crypto asset (BTC, ETH, etc.) for specialized handling
            **kwargs: Passed to NumericTransformer
        """
        super().__init__(**kwargs)
        self.asset_type = asset_type.upper() if asset_type else None

    def transform_from_satoshi(self, sats: Union[int, str, Decimal]) -> NumericResult:
        """Convert satoshi to BTC."""
        result = self.transform(sats)
        if result.success and result.value is not None:
            btc_value = result.value / self.SATOSHI_FACTOR
            return NumericResult(
                success=True,
                value=btc_value.quantize(self._quantize, rounding=self.rounding),
                original=sats,
                precision=self._get_precision(btc_value),
            )
        return result

    def transform_from_wei(self, wei: Union[int, str, Decimal]) -> NumericResult:
        """Convert wei to ETH."""
        result = self.transform(wei)
        if result.success and result.value is not None:
            eth_value = result.value / self.WEI_FACTOR
            return NumericResult(
                success=True,
                value=eth_value.quantize(self._quantize, rounding=self.rounding),
                original=wei,
                precision=self._get_precision(eth_value),
            )
        return result


class FiatAmountTransformer(NumericTransformer):
    """
    Specialized transformer for fiat currency amounts.

    Handles:
    - Standard 2 decimal places for most currencies
    - Currency-specific precision (JPY = 0, BHD = 3)
    - Automatic currency detection and stripping
    """

    # Currency precision overrides (default is 2)
    CURRENCY_PRECISION = {
        'JPY': 0, 'KRW': 0, 'VND': 0,  # Zero decimal
        'BHD': 3, 'KWD': 3, 'OMR': 3,  # Three decimal
    }

    def __init__(self, currency: str = 'USD', **kwargs):
        """
        Initialize fiat amount transformer.

        Args:
            currency: ISO 4217 currency code
            **kwargs: Passed to NumericTransformer
        """
        precision = self.CURRENCY_PRECISION.get(currency.upper(), 2)
        super().__init__(max_precision=precision, **kwargs)
        self.currency = currency.upper()


def transform_amount(
    value: Any,
    precision: int = 20,
    allow_negative: bool = True,
) -> Optional[Decimal]:
    """
    Convenience function to transform a single amount.

    Args:
        value: Input value
        precision: Maximum decimal places
        allow_negative: Allow negative values

    Returns:
        Decimal value or None on failure
    """
    transformer = NumericTransformer(
        max_precision=precision,
        allow_negative=allow_negative,
    )
    result = transformer.transform(value)
    return result.value if result.success else None


def format_xsd_decimal(value: Decimal) -> str:
    """
    Format Decimal for XSD output.

    Args:
        value: Decimal value

    Returns:
        XSD-compliant string representation
    """
    if value is None:
        return ""
    # Remove trailing zeros, scientific notation
    normalized = value.normalize()
    return format(normalized, 'f')


if __name__ == "__main__":
    print("CARFul Numeric Transformer")
    print("=" * 50)

    # Test various formats
    transformer = NumericTransformer()

    test_values = [
        "123.456",
        "1,234.56",
        "$999.99",
        "1.5e-8",
        "0.00000000000000000001",  # 20 decimal places
        "-42.5",
        "(100.00)",  # Accounting notation
        "1 234 567.89",  # European thousands
    ]

    print("\nTest transformations:")
    for val in test_values:
        result = transformer.transform(val)
        status = "✓" if result.success else "✗"
        print(f"  {status} '{val}' → {result.value} (precision: {result.precision})")
