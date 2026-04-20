"""
CARFul TIN Validation Module

Provides jurisdiction-specific Tax Identification Number validation:
    - US EIN: Employer Identification Number
    - UK UTR: Unique Taxpayer Reference (Modulus 11)
    - CA SIN: Social Insurance Number (Luhn algorithm)
    - NOTIN: Handler for unknown/unavailable TINs

Usage:
    from validators.tin import TINDispatcher, validate_tin

    # Validate a TIN
    result = validate_tin('12-3456789', 'US')
    if result.is_valid:
        print(f"Valid {result.tin_type}")
    else:
        print(f"Invalid: {result.error}")

    # Use dispatcher directly
    dispatcher = TINDispatcher()
    result = dispatcher.validate('123456789012', 'GB')
"""

from .dispatcher import (
    TINDispatcher,
    TINValidationResult,
    validate_tin,
)

from .us_ein import (
    EINValidator,
    is_valid_ein,
)

from .uk_utr import (
    UTRValidator,
    is_valid_utr,
)

from .ca_sin import (
    SINValidator,
    is_valid_sin,
)

from .notin import (
    NOTINHandler,
    create_notin_element,
)

__all__ = [
    # Dispatcher
    'TINDispatcher',
    'TINValidationResult',
    'validate_tin',
    # US EIN
    'EINValidator',
    'is_valid_ein',
    # UK UTR
    'UTRValidator',
    'is_valid_utr',
    # CA SIN
    'SINValidator',
    'is_valid_sin',
    # NOTIN
    'NOTINHandler',
    'create_notin_element',
]
