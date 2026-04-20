"""
CARFul - US EIN (Employer Identification Number) Validator

Validates US Employer Identification Numbers per IRS specifications.
Format: XX-XXXXXXX (9 digits with optional hyphen after 2nd digit)

Validation rules:
    - Must be 9 digits (with optional hyphen)
    - First 2 digits are IRS Campus Code (prefix)
    - Invalid prefixes: 00, 07, 08, 09, 17, 18, 19, 79, 89, 96, 97
    - Suspicious patterns flagged: all same digits, sequential

Usage:
    from validators.tin.us_ein import EINValidator, is_valid_ein

    validator = EINValidator()
    result = validator.validate('12-3456789')

    if result.is_valid:
        print(f"Valid EIN: {result.normalized}")
    else:
        print(f"Invalid: {result.error}")

    # Quick check
    if is_valid_ein('12-3456789'):
        print("Valid!")
"""

import re
from typing import Optional
from dataclasses import dataclass


# =============================================================================
# Constants
# =============================================================================

# Invalid IRS Campus Code prefixes
# These prefixes have never been assigned or are reserved
INVALID_PREFIXES = {
    '00',  # Never assigned
    '07', '08', '09',  # Reserved
    '17', '18', '19',  # Reserved
    '79',  # Reserved
    '89',  # Reserved
    '96', '97',  # Reserved for IRS use
}

# IRS Campus Code to location mapping (for informational purposes)
CAMPUS_CODES = {
    '01': 'Small Business/Self-Employed (Austin)',
    '02': 'Small Business/Self-Employed (Austin)',
    '03': 'Small Business/Self-Employed (Austin)',
    '04': 'Small Business/Self-Employed (Austin)',
    '05': 'Small Business/Self-Employed (Austin)',
    '06': 'Small Business/Self-Employed (Austin)',
    '10': 'Small Business/Self-Employed (Ogden)',
    '11': 'Small Business/Self-Employed (Ogden)',
    '12': 'Small Business/Self-Employed (Ogden)',
    '13': 'Andover Campus',
    '14': 'Andover Campus',
    '15': 'Andover Campus',
    '16': 'Andover Campus',
    '20': 'Internet',
    '21': 'Internet',
    '22': 'Internet',
    '23': 'Internet',
    '24': 'Internet',
    '25': 'Internet',
    '26': 'Internet',
    '27': 'Internet',
    '30': 'Atlanta Campus',
    '31': 'Atlanta Campus',
    '32': 'Atlanta Campus',
    '33': 'IRS Online',
    '34': 'IRS Online',
    '35': 'Philadelphia Campus',
    '36': 'Philadelphia Campus',
    '37': 'Philadelphia Campus',
    '38': 'Philadelphia Campus',
    '39': 'Philadelphia Campus',
    '40': 'Kansas City Campus',
    '41': 'Kansas City Campus',
    '42': 'Kansas City Campus',
    '43': 'Kansas City Campus',
    '44': 'Brookhaven Campus',
    '45': 'Brookhaven Campus',
    '46': 'Brookhaven Campus',
    '47': 'Brookhaven Campus',
    '48': 'Brookhaven Campus',
    '50': 'Cincinnati Campus',
    '51': 'Cincinnati Campus',
    '52': 'Cincinnati Campus',
    '53': 'Cincinnati Campus',
    '54': 'Cincinnati Campus',
    '55': 'Cincinnati Campus',
    '56': 'Cincinnati Campus',
    '57': 'Cincinnati Campus',
    '58': 'Cincinnati Campus',
    '59': 'Cincinnati Campus',
    '60': 'Fresno Campus',
    '61': 'Fresno Campus',
    '62': 'Fresno Campus',
    '63': 'Fresno Campus',
    '64': 'Fresno Campus',
    '65': 'Fresno Campus',
    '66': 'Fresno Campus',
    '67': 'Small Business/Self-Employed (Ogden)',
    '68': 'Memphis Campus',
    '71': 'Memphis Campus',
    '72': 'Memphis Campus',
    '73': 'Memphis Campus',
    '74': 'Memphis Campus',
    '75': 'Memphis Campus',
    '76': 'Memphis Campus',
    '77': 'Memphis Campus',
    '80': 'Ogden Campus',
    '81': 'Ogden Campus',
    '82': 'Ogden Campus',
    '83': 'Ogden Campus',
    '84': 'Ogden Campus',
    '85': 'Ogden Campus',
    '86': 'Ogden Campus',
    '87': 'Ogden Campus',
    '88': 'Ogden Campus',
    '90': 'Ogden Campus',
    '91': 'Ogden Campus',
    '92': 'Ogden Campus',
    '93': 'Ogden Campus',
    '94': 'Ogden Campus',
    '95': 'Ogden Campus',
    '98': 'Ogden Campus',
    '99': 'Ogden Campus',
}

# Suspicious patterns (flood-fill and sequential)
SUSPICIOUS_PATTERNS = [
    '111111111', '222222222', '333333333', '444444444',
    '555555555', '666666666', '777777777', '888888888', '999999999',
    '123456789', '987654321',
]


# =============================================================================
# Validation Result
# =============================================================================

@dataclass
class EINValidationResult:
    """
    Result of EIN validation.

    Attributes:
        is_valid: True if EIN passed all validation checks
        normalized: EIN in XX-XXXXXXX format
        digits_only: EIN as 9 digits without hyphen
        prefix: First 2 digits (IRS Campus Code)
        campus: IRS campus location (if known)
        error: Error message if invalid
        warning: Warning message for suspicious patterns
    """
    is_valid: bool
    normalized: Optional[str] = None
    digits_only: Optional[str] = None
    prefix: Optional[str] = None
    campus: Optional[str] = None
    error: Optional[str] = None
    warning: Optional[str] = None

    @property
    def has_warning(self) -> bool:
        """Check if there's a warning."""
        return self.warning is not None


# =============================================================================
# EIN Validator
# =============================================================================

class EINValidator:
    """
    Validator for US Employer Identification Numbers (EIN).

    Validates format, IRS campus code prefix, and checks for
    suspicious patterns.

    Example:
        validator = EINValidator()

        result = validator.validate('12-3456789')
        if result.is_valid:
            print(f"Campus: {result.campus}")

        result = validator.validate('00-1234567')
        if not result.is_valid:
            print(f"Error: {result.error}")
    """

    # Regex patterns
    EIN_WITH_HYPHEN = re.compile(r'^(\d{2})-(\d{7})$')
    EIN_DIGITS_ONLY = re.compile(r'^(\d{9})$')

    def __init__(self, strict: bool = True):
        """
        Initialize EIN validator.

        Args:
            strict: If True, flag suspicious patterns as warnings
        """
        self.strict = strict

    def _normalize(self, ein: str) -> Optional[str]:
        """
        Normalize EIN to XX-XXXXXXX format.

        Returns None if input cannot be normalized.
        """
        ein = ein.strip()

        # Try with hyphen
        match = self.EIN_WITH_HYPHEN.match(ein)
        if match:
            return ein

        # Try digits only
        match = self.EIN_DIGITS_ONLY.match(ein)
        if match:
            digits = match.group(1)
            return f"{digits[:2]}-{digits[2:]}"

        return None

    def _extract_digits(self, ein: str) -> Optional[str]:
        """Extract 9 digits from EIN."""
        digits = re.sub(r'\D', '', ein)
        return digits if len(digits) == 9 else None

    def _validate_prefix(self, prefix: str) -> Optional[str]:
        """
        Validate IRS campus code prefix.

        Returns error message if invalid, None if valid.
        """
        if prefix in INVALID_PREFIXES:
            return f"Invalid EIN: Prefix '{prefix}' is reserved/never assigned"
        return None

    def _check_suspicious_patterns(self, digits: str) -> Optional[str]:
        """
        Check for suspicious patterns.

        Returns warning message if suspicious, None otherwise.
        """
        if digits in SUSPICIOUS_PATTERNS:
            return f"Suspicious pattern detected: {digits} appears to be a test/placeholder EIN"

        # Check for all same digits (except those already in SUSPICIOUS_PATTERNS)
        if len(set(digits)) == 1:
            return f"Suspicious pattern: All digits are the same ({digits[0]})"

        return None

    def validate(self, ein: str) -> EINValidationResult:
        """
        Validate a US EIN.

        Args:
            ein: EIN to validate (with or without hyphen)

        Returns:
            EINValidationResult with validation details
        """
        if not ein or not ein.strip():
            return EINValidationResult(
                is_valid=False,
                error="EIN cannot be empty",
            )

        # Normalize
        normalized = self._normalize(ein)
        if normalized is None:
            return EINValidationResult(
                is_valid=False,
                error="Invalid EIN format. Expected XX-XXXXXXX or 9 digits",
            )

        # Extract components
        digits = self._extract_digits(normalized)
        prefix = digits[:2]
        campus = CAMPUS_CODES.get(prefix)

        # Validate prefix
        prefix_error = self._validate_prefix(prefix)
        if prefix_error:
            return EINValidationResult(
                is_valid=False,
                normalized=normalized,
                digits_only=digits,
                prefix=prefix,
                error=prefix_error,
            )

        # Check suspicious patterns
        warning = None
        if self.strict:
            warning = self._check_suspicious_patterns(digits)

        return EINValidationResult(
            is_valid=True,
            normalized=normalized,
            digits_only=digits,
            prefix=prefix,
            campus=campus,
            warning=warning,
        )


# =============================================================================
# Convenience Functions
# =============================================================================

def is_valid_ein(ein: str) -> bool:
    """
    Quick check if EIN is valid.

    Args:
        ein: EIN to validate

    Returns:
        True if valid, False otherwise
    """
    validator = EINValidator(strict=False)
    return validator.validate(ein).is_valid


def validate_ein(ein: str, strict: bool = True) -> EINValidationResult:
    """
    Validate a US EIN with full result.

    Args:
        ein: EIN to validate
        strict: Flag suspicious patterns

    Returns:
        EINValidationResult
    """
    return EINValidator(strict=strict).validate(ein)


def get_ein_campus(ein: str) -> Optional[str]:
    """
    Get IRS campus location for an EIN.

    Args:
        ein: Valid EIN

    Returns:
        Campus location or None if unknown
    """
    result = validate_ein(ein, strict=False)
    return result.campus if result.is_valid else None
