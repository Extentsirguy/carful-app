"""
CARFul - TIN Validation Dispatcher

Routes TIN validation to the appropriate country-specific validator
based on the country code. Supports US EIN, UK UTR, CA SIN, and
generic validation for other jurisdictions.

Usage:
    from validators.tin import TINDispatcher, validate_tin

    dispatcher = TINDispatcher()

    # Validate US EIN
    result = dispatcher.validate('12-3456789', 'US')

    # Validate UK UTR
    result = dispatcher.validate('1234567890', 'GB')

    # Validate Canadian SIN
    result = dispatcher.validate('123-456-782', 'CA')

    # Generic validation (other countries)
    result = dispatcher.validate('ABC123456', 'DE')

    # Convenience function
    result = validate_tin('12-3456789', 'US')
"""

import re
from typing import Optional, Dict, Callable
from dataclasses import dataclass
from enum import Enum

from .us_ein import EINValidator
from .uk_utr import UTRValidator
from .ca_sin import SINValidator
from .notin import NOTINHandler, is_notin


# =============================================================================
# TIN Types
# =============================================================================

class TINType(Enum):
    """Types of Tax Identification Numbers."""
    US_EIN = 'US EIN'
    UK_UTR = 'UK UTR'
    CA_SIN = 'CA SIN'
    GENERIC = 'Generic'
    NOTIN = 'NOTIN'


# =============================================================================
# Validation Result
# =============================================================================

@dataclass
class TINValidationResult:
    """
    Result of TIN validation from dispatcher.

    Attributes:
        is_valid: True if TIN passed validation
        value: Original TIN value
        normalized: Normalized TIN format
        country: Country code
        tin_type: Type of TIN (US_EIN, UK_UTR, etc.)
        is_notin: True if this is a NOTIN case
        error: Error message if invalid
        warning: Warning message (e.g., suspicious pattern)
        details: Additional validation details
    """
    is_valid: bool
    value: str
    normalized: Optional[str] = None
    country: str = ''
    tin_type: TINType = TINType.GENERIC
    is_notin: bool = False
    error: Optional[str] = None
    warning: Optional[str] = None
    details: Optional[Dict] = None

    def to_xml_attrs(self) -> dict:
        """
        Get attributes for XML TIN element.

        Returns:
            Dictionary with 'issuedBy' and optionally 'unknown'
        """
        attrs = {'issuedBy': self.country}
        if self.is_notin:
            attrs['unknown'] = 'true'
        return attrs


# =============================================================================
# Generic TIN Validator
# =============================================================================

class GenericTINValidator:
    """
    Generic TIN validator for jurisdictions without specific validators.

    Performs basic format validation:
    - Minimum/maximum length
    - Alphanumeric characters only
    - No suspicious patterns
    """

    MIN_LENGTH = 5
    MAX_LENGTH = 20

    def validate(self, tin: str, country: str) -> TINValidationResult:
        """
        Validate a TIN with generic rules.

        Args:
            tin: TIN to validate
            country: Country code

        Returns:
            TINValidationResult
        """
        if not tin or not tin.strip():
            return TINValidationResult(
                is_valid=False,
                value=tin or '',
                country=country,
                tin_type=TINType.GENERIC,
                error="TIN cannot be empty",
            )

        normalized = tin.strip().upper()

        # Check length
        if len(normalized) < self.MIN_LENGTH:
            return TINValidationResult(
                is_valid=False,
                value=tin,
                normalized=normalized,
                country=country,
                tin_type=TINType.GENERIC,
                error=f"TIN too short (minimum {self.MIN_LENGTH} characters)",
            )

        if len(normalized) > self.MAX_LENGTH:
            return TINValidationResult(
                is_valid=False,
                value=tin,
                normalized=normalized,
                country=country,
                tin_type=TINType.GENERIC,
                error=f"TIN too long (maximum {self.MAX_LENGTH} characters)",
            )

        # Check for valid characters (alphanumeric plus common separators)
        if not re.match(r'^[A-Za-z0-9\-\s./]+$', normalized):
            return TINValidationResult(
                is_valid=False,
                value=tin,
                normalized=normalized,
                country=country,
                tin_type=TINType.GENERIC,
                error="TIN contains invalid characters",
            )

        return TINValidationResult(
            is_valid=True,
            value=tin,
            normalized=normalized,
            country=country,
            tin_type=TINType.GENERIC,
        )


# =============================================================================
# TIN Dispatcher
# =============================================================================

class TINDispatcher:
    """
    Dispatcher for TIN validation.

    Routes validation to the appropriate country-specific validator
    based on the country code.

    Supported validators:
        - US: EIN (Employer Identification Number)
        - GB: UTR (Unique Taxpayer Reference)
        - CA: SIN (Social Insurance Number)
        - Others: Generic validation

    Example:
        dispatcher = TINDispatcher()

        # US EIN
        result = dispatcher.validate('12-3456789', 'US')
        print(result.tin_type)  # TINType.US_EIN

        # UK UTR
        result = dispatcher.validate('1234567890', 'GB')
        print(result.tin_type)  # TINType.UK_UTR

        # Other country
        result = dispatcher.validate('DE123456789', 'DE')
        print(result.tin_type)  # TINType.GENERIC
    """

    def __init__(self):
        """Initialize dispatcher with country-specific validators."""
        self.ein_validator = EINValidator()
        self.utr_validator = UTRValidator()
        self.sin_validator = SINValidator()
        self.generic_validator = GenericTINValidator()
        self.notin_handler = NOTINHandler()

        # Country code to validator mapping
        self._validators: Dict[str, Callable] = {
            'US': self._validate_us,
            'GB': self._validate_uk,
            'UK': self._validate_uk,  # Alias
            'CA': self._validate_ca,
        }

    def _validate_us(self, tin: str, country: str) -> TINValidationResult:
        """Validate US EIN."""
        result = self.ein_validator.validate(tin)

        return TINValidationResult(
            is_valid=result.is_valid,
            value=tin,
            normalized=result.normalized,
            country=country,
            tin_type=TINType.US_EIN,
            error=result.error,
            warning=result.warning,
            details={
                'prefix': result.prefix,
                'campus': result.campus,
            } if result.is_valid else None,
        )

    def _validate_uk(self, tin: str, country: str) -> TINValidationResult:
        """Validate UK UTR."""
        result = self.utr_validator.validate(tin)

        return TINValidationResult(
            is_valid=result.is_valid,
            value=tin,
            normalized=result.normalized,
            country='GB',  # Normalize to GB
            tin_type=TINType.UK_UTR,
            error=result.error,
            details={
                'check_digit': result.check_digit,
            } if result.is_valid else None,
        )

    def _validate_ca(self, tin: str, country: str) -> TINValidationResult:
        """Validate Canadian SIN."""
        result = self.sin_validator.validate(tin)

        return TINValidationResult(
            is_valid=result.is_valid,
            value=tin,
            normalized=result.normalized,
            country=country,
            tin_type=TINType.CA_SIN,
            error=result.error,
            warning=result.warning,
            details={
                'province_code': result.province_code,
                'region': result.region,
                'is_temporary': result.is_temporary,
            } if result.is_valid else None,
        )

    def validate(
        self,
        tin: Optional[str],
        country: str,
    ) -> TINValidationResult:
        """
        Validate a TIN for a specific country.

        Args:
            tin: TIN value to validate
            country: ISO 3166-1 Alpha-2 country code

        Returns:
            TINValidationResult with validation details
        """
        country = country.upper() if country else 'XX'

        # Check for NOTIN
        if self.notin_handler.is_notin(tin):
            return TINValidationResult(
                is_valid=True,  # NOTIN is valid (acceptable)
                value=tin or '',
                normalized='NOTIN',
                country=country,
                tin_type=TINType.NOTIN,
                is_notin=True,
            )

        # Get country-specific validator
        validator = self._validators.get(country)

        if validator:
            return validator(tin, country)
        else:
            return self.generic_validator.validate(tin, country)

    def get_supported_countries(self) -> list:
        """Get list of countries with specific validators."""
        return list(self._validators.keys())


# =============================================================================
# Convenience Functions
# =============================================================================

_dispatcher = TINDispatcher()


def validate_tin(
    tin: Optional[str],
    country: str,
) -> TINValidationResult:
    """
    Validate a TIN for a specific country.

    Convenience function that uses the default dispatcher.

    Args:
        tin: TIN value to validate
        country: Country code

    Returns:
        TINValidationResult
    """
    return _dispatcher.validate(tin, country)


def get_tin_type(country: str) -> TINType:
    """
    Get the TIN type for a country.

    Args:
        country: Country code

    Returns:
        TINType enum value
    """
    country = country.upper()

    if country == 'US':
        return TINType.US_EIN
    elif country in ('GB', 'UK'):
        return TINType.UK_UTR
    elif country == 'CA':
        return TINType.CA_SIN
    else:
        return TINType.GENERIC
