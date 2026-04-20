"""
CARFul - Canadian SIN (Social Insurance Number) Validator

Validates Canadian Social Insurance Numbers using the Luhn algorithm.
Format: XXX-XXX-XXX or XXXXXXXXX (9 digits)

Validation rules:
    - Must be exactly 9 digits
    - Passes Luhn algorithm check digit validation
    - First digit indicates province/region (optional validation)

Province codes (first digit):
    1: Atlantic provinces (NB, NS, PE, NL)
    2: Quebec
    3: Quebec
    4: Ontario (including overseas residents)
    5: Ontario
    6: Prairie provinces (MB, SK, AB, NT, NU)
    7: Pacific (BC, YT)
    8: Not used
    9: Temporary SIN (non-residents)

Usage:
    from validators.tin.ca_sin import SINValidator, is_valid_sin

    validator = SINValidator()
    result = validator.validate('123-456-782')

    if result.is_valid:
        print(f"Valid SIN from {result.region}")
    else:
        print(f"Invalid: {result.error}")
"""

import re
from typing import Optional
from dataclasses import dataclass


# =============================================================================
# Constants
# =============================================================================

# Province code to region mapping
PROVINCE_CODES = {
    '1': 'Atlantic provinces (NB, NS, PE, NL)',
    '2': 'Quebec',
    '3': 'Quebec',
    '4': 'Ontario (including overseas)',
    '5': 'Ontario',
    '6': 'Prairie provinces (MB, SK, AB, NT, NU)',
    '7': 'Pacific (BC, YT)',
    '8': 'Not assigned',
    '9': 'Temporary SIN (non-residents)',
}

# Province codes by region (for mismatch warnings)
ATLANTIC_CODES = {'1'}
QUEBEC_CODES = {'2', '3'}
ONTARIO_CODES = {'4', '5'}
PRAIRIE_CODES = {'6'}
PACIFIC_CODES = {'7'}
TEMPORARY_CODES = {'9'}


# =============================================================================
# Validation Result
# =============================================================================

@dataclass
class SINValidationResult:
    """
    Result of SIN validation.

    Attributes:
        is_valid: True if SIN passed all validation checks
        normalized: SIN in XXX-XXX-XXX format
        digits_only: SIN as 9 digits
        province_code: First digit (province indicator)
        region: Province/region name
        is_temporary: True if this is a temporary SIN (starts with 9)
        error: Error message if invalid
        warning: Warning message (e.g., province mismatch)
    """
    is_valid: bool
    normalized: Optional[str] = None
    digits_only: Optional[str] = None
    province_code: Optional[str] = None
    region: Optional[str] = None
    is_temporary: bool = False
    error: Optional[str] = None
    warning: Optional[str] = None


# =============================================================================
# Luhn Algorithm
# =============================================================================

def luhn_checksum(digits: str) -> int:
    """
    Calculate the Luhn checksum for a digit string.

    The Luhn algorithm:
    1. From right to left, double every second digit
    2. If doubling results in > 9, subtract 9
    3. Sum all digits
    4. Valid if sum % 10 == 0

    Args:
        digits: String of digits

    Returns:
        Checksum value (0-9)
    """
    total = 0
    parity = len(digits) % 2

    for i, digit in enumerate(digits):
        d = int(digit)

        if i % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9

        total += d

    return total % 10


def is_valid_luhn(digits: str) -> bool:
    """
    Check if a digit string passes Luhn validation.

    Args:
        digits: String of digits

    Returns:
        True if valid
    """
    if not digits or not digits.isdigit():
        return False

    return luhn_checksum(digits) == 0


def compute_luhn_check_digit(digits: str) -> int:
    """
    Compute the Luhn check digit for a prefix.

    Args:
        digits: String of digits (without check digit)

    Returns:
        Check digit (0-9)
    """
    # Append 0 as placeholder and calculate
    checksum = luhn_checksum(digits + '0')
    return (10 - checksum) % 10


# =============================================================================
# SIN Validator
# =============================================================================

class SINValidator:
    """
    Validator for Canadian Social Insurance Numbers (SIN).

    Validates format, Luhn check digit, and optionally checks
    for province code consistency.

    Example:
        validator = SINValidator()

        result = validator.validate('123-456-782')
        if result.is_valid:
            print(f"Region: {result.region}")

        # Validate with address province
        result = validator.validate('123-456-782', address_province='ON')
    """

    # Regex patterns
    SIN_WITH_HYPHENS = re.compile(r'^(\d{3})-(\d{3})-(\d{3})$')
    SIN_WITH_SPACES = re.compile(r'^(\d{3})\s+(\d{3})\s+(\d{3})$')
    SIN_DIGITS_ONLY = re.compile(r'^(\d{9})$')

    # Province code to province abbreviation mapping
    PROVINCE_TO_CODE = {
        'NB': '1', 'NS': '1', 'PE': '1', 'NL': '1',  # Atlantic
        'QC': '2',  # Quebec (primary)
        'ON': '4',  # Ontario (primary)
        'MB': '6', 'SK': '6', 'AB': '6', 'NT': '6', 'NU': '6',  # Prairie
        'BC': '7', 'YT': '7',  # Pacific
    }

    def __init__(self, check_province: bool = True):
        """
        Initialize SIN validator.

        Args:
            check_province: If True, warn on province code mismatch
        """
        self.check_province = check_province

    def _normalize(self, sin: str) -> Optional[str]:
        """
        Normalize SIN to XXX-XXX-XXX format.

        Returns None if cannot be normalized.
        """
        sin = sin.strip()

        # Try with hyphens
        match = self.SIN_WITH_HYPHENS.match(sin)
        if match:
            return sin

        # Try with spaces
        match = self.SIN_WITH_SPACES.match(sin)
        if match:
            return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"

        # Try digits only
        match = self.SIN_DIGITS_ONLY.match(sin)
        if match:
            d = match.group(1)
            return f"{d[:3]}-{d[3:6]}-{d[6:]}"

        # Try removing all non-digits
        digits = re.sub(r'\D', '', sin)
        if len(digits) == 9:
            return f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"

        return None

    def _extract_digits(self, sin: str) -> str:
        """Extract 9 digits from normalized SIN."""
        return re.sub(r'\D', '', sin)

    def _check_province_mismatch(
        self,
        province_code: str,
        address_province: str,
    ) -> Optional[str]:
        """
        Check if SIN province code matches address province.

        Returns warning message if mismatch, None otherwise.
        """
        expected_code = self.PROVINCE_TO_CODE.get(address_province.upper())

        if expected_code is None:
            return None  # Unknown province, can't check

        # Handle Quebec which has two codes
        if address_province.upper() == 'QC' and province_code in QUEBEC_CODES:
            return None

        # Handle Ontario which has two codes
        if address_province.upper() == 'ON' and province_code in ONTARIO_CODES:
            return None

        if province_code != expected_code:
            return (
                f"SIN province code ({province_code}) does not match "
                f"address province ({address_province})"
            )

        return None

    def validate(
        self,
        sin: str,
        address_province: Optional[str] = None,
    ) -> SINValidationResult:
        """
        Validate a Canadian SIN.

        Args:
            sin: SIN to validate
            address_province: Optional province code for mismatch warning

        Returns:
            SINValidationResult with validation details
        """
        if not sin or not sin.strip():
            return SINValidationResult(
                is_valid=False,
                error="SIN cannot be empty",
            )

        # Normalize
        normalized = self._normalize(sin)
        if normalized is None:
            return SINValidationResult(
                is_valid=False,
                error="Invalid SIN format. Expected XXX-XXX-XXX or 9 digits",
            )

        # Extract digits
        digits = self._extract_digits(normalized)
        province_code = digits[0]
        region = PROVINCE_CODES.get(province_code, 'Unknown')
        is_temporary = province_code == '9'

        # Check for unused code
        if province_code == '8':
            return SINValidationResult(
                is_valid=False,
                normalized=normalized,
                digits_only=digits,
                province_code=province_code,
                region=region,
                error="Invalid SIN: Province code 8 is not assigned",
            )

        # Validate with Luhn algorithm
        if not is_valid_luhn(digits):
            # Calculate what the check digit should be
            expected = compute_luhn_check_digit(digits[:8])
            return SINValidationResult(
                is_valid=False,
                normalized=normalized,
                digits_only=digits,
                province_code=province_code,
                region=region,
                is_temporary=is_temporary,
                error=f"Invalid SIN: Luhn check failed (check digit should be {expected})",
            )

        # Check province mismatch (warning only)
        warning = None
        if self.check_province and address_province:
            warning = self._check_province_mismatch(province_code, address_province)

        return SINValidationResult(
            is_valid=True,
            normalized=normalized,
            digits_only=digits,
            province_code=province_code,
            region=region,
            is_temporary=is_temporary,
            warning=warning,
        )


# =============================================================================
# Convenience Functions
# =============================================================================

def is_valid_sin(sin: str) -> bool:
    """
    Quick check if SIN is valid.

    Args:
        sin: SIN to validate

    Returns:
        True if valid, False otherwise
    """
    return SINValidator(check_province=False).validate(sin).is_valid


def validate_sin(
    sin: str,
    address_province: Optional[str] = None,
) -> SINValidationResult:
    """
    Validate a Canadian SIN with full result.

    Args:
        sin: SIN to validate
        address_province: Optional province for mismatch check

    Returns:
        SINValidationResult
    """
    return SINValidator().validate(sin, address_province)
