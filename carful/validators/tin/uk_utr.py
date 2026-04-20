"""
CARFul - UK UTR (Unique Taxpayer Reference) Validator

Validates UK Unique Taxpayer References per HMRC specifications.
Format: 10 digits with Modulus 11 check digit algorithm.

The UTR is used by HMRC for self-assessment tax returns and
company tax returns.

Validation rules:
    - Must be exactly 10 digits
    - Passes Modulus 11 check digit validation
    - First digit cannot be 0

Usage:
    from validators.tin.uk_utr import UTRValidator, is_valid_utr

    validator = UTRValidator()
    result = validator.validate('1234567890')

    if result.is_valid:
        print("Valid UTR")
    else:
        print(f"Invalid: {result.error}")
"""

import re
from typing import Optional
from dataclasses import dataclass


# =============================================================================
# Validation Result
# =============================================================================

@dataclass
class UTRValidationResult:
    """
    Result of UTR validation.

    Attributes:
        is_valid: True if UTR passed all validation checks
        normalized: UTR as 10 digits
        check_digit: The check digit (last digit)
        computed_check_digit: What the check digit should be
        error: Error message if invalid
    """
    is_valid: bool
    normalized: Optional[str] = None
    check_digit: Optional[str] = None
    computed_check_digit: Optional[str] = None
    error: Optional[str] = None


# =============================================================================
# Modulus 11 Algorithm
# =============================================================================

def modulus_11_check(digits: str) -> bool:
    """
    Validate a UTR using the Modulus 11 algorithm.

    The Modulus 11 algorithm works as follows:
    1. Each digit is multiplied by a weight (6, 7, 8, 9, 10, 5, 4, 3, 2 for positions 1-9)
    2. The products are summed
    3. The sum is divided by 11
    4. The check digit is 11 minus the remainder
    5. If check digit is 10, it becomes 'K' (but UTR uses only digits, so this is invalid)
    6. If check digit is 11, it becomes 0

    Args:
        digits: 10-digit UTR string

    Returns:
        True if check digit is valid
    """
    if len(digits) != 10 or not digits.isdigit():
        return False

    # Weights for positions 1-9 (the last digit is the check digit)
    weights = [6, 7, 8, 9, 10, 5, 4, 3, 2]

    # Calculate weighted sum of first 9 digits
    total = sum(int(d) * w for d, w in zip(digits[:9], weights))

    # Calculate remainder
    remainder = total % 11

    # Calculate expected check digit
    if remainder == 0:
        expected_check = 0
    else:
        expected_check = 11 - remainder

    # Check digit 10 is invalid for UTR (would be 'K' or 'X' in other schemes)
    if expected_check == 10:
        return False

    # Compare with actual check digit
    actual_check = int(digits[9])

    return expected_check == actual_check


def compute_check_digit(digits: str) -> Optional[int]:
    """
    Compute the Modulus 11 check digit for a 9-digit UTR prefix.

    Args:
        digits: First 9 digits of UTR

    Returns:
        Check digit (0-9) or None if check digit would be 10
    """
    if len(digits) != 9 or not digits.isdigit():
        return None

    weights = [6, 7, 8, 9, 10, 5, 4, 3, 2]
    total = sum(int(d) * w for d, w in zip(digits, weights))
    remainder = total % 11

    if remainder == 0:
        return 0
    else:
        check = 11 - remainder
        return None if check == 10 else check


# =============================================================================
# UTR Validator
# =============================================================================

class UTRValidator:
    """
    Validator for UK Unique Taxpayer References (UTR).

    Validates format and Modulus 11 check digit.

    Example:
        validator = UTRValidator()

        result = validator.validate('1234567890')
        if result.is_valid:
            print("Valid UTR")
        else:
            print(f"Error: {result.error}")
    """

    # Regex pattern for 10 digits
    UTR_PATTERN = re.compile(r'^(\d{10})$')

    # Alternative patterns (with spaces)
    UTR_SPACED_PATTERN = re.compile(r'^(\d{5})\s*(\d{5})$')

    def _normalize(self, utr: str) -> Optional[str]:
        """
        Normalize UTR to 10-digit format.

        Handles:
            - 10 digits: 1234567890
            - 10 digits with space: 12345 67890

        Returns None if cannot be normalized.
        """
        utr = utr.strip()

        # Try direct 10 digits
        match = self.UTR_PATTERN.match(utr)
        if match:
            return match.group(1)

        # Try spaced format
        match = self.UTR_SPACED_PATTERN.match(utr)
        if match:
            return match.group(1) + match.group(2)

        # Try removing all non-digits
        digits = re.sub(r'\D', '', utr)
        if len(digits) == 10:
            return digits

        return None

    def validate(self, utr: str) -> UTRValidationResult:
        """
        Validate a UK UTR.

        Args:
            utr: UTR to validate

        Returns:
            UTRValidationResult with validation details
        """
        if not utr or not utr.strip():
            return UTRValidationResult(
                is_valid=False,
                error="UTR cannot be empty",
            )

        # Normalize
        normalized = self._normalize(utr)
        if normalized is None:
            return UTRValidationResult(
                is_valid=False,
                error="Invalid UTR format. Expected 10 digits",
            )

        # Check first digit is not 0
        if normalized[0] == '0':
            return UTRValidationResult(
                is_valid=False,
                normalized=normalized,
                error="Invalid UTR: First digit cannot be 0",
            )

        # Get check digit info
        actual_check = normalized[9]
        computed = compute_check_digit(normalized[:9])

        # Validate with Modulus 11
        if not modulus_11_check(normalized):
            computed_str = str(computed) if computed is not None else 'N/A'
            return UTRValidationResult(
                is_valid=False,
                normalized=normalized,
                check_digit=actual_check,
                computed_check_digit=computed_str,
                error=f"Invalid UTR: Check digit validation failed (expected {computed_str}, got {actual_check})",
            )

        return UTRValidationResult(
            is_valid=True,
            normalized=normalized,
            check_digit=actual_check,
            computed_check_digit=str(computed) if computed is not None else actual_check,
        )


# =============================================================================
# Convenience Functions
# =============================================================================

def is_valid_utr(utr: str) -> bool:
    """
    Quick check if UTR is valid.

    Args:
        utr: UTR to validate

    Returns:
        True if valid, False otherwise
    """
    return UTRValidator().validate(utr).is_valid


def validate_utr(utr: str) -> UTRValidationResult:
    """
    Validate a UK UTR with full result.

    Args:
        utr: UTR to validate

    Returns:
        UTRValidationResult
    """
    return UTRValidator().validate(utr)
