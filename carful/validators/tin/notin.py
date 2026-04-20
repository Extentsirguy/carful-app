"""
CARFul - NOTIN Handler

Handles cases where Tax Identification Numbers are not available.
Per OECD CARF specification, when TIN is unavailable, the XML should
contain: <TIN issuedBy="XX" unknown="true">NOTIN</TIN>

Usage:
    from validators.tin.notin import NOTINHandler, create_notin_element

    handler = NOTINHandler()

    # Check if value indicates NOTIN
    if handler.is_notin(''):
        tin_data = handler.create_notin_data('US')

    # Create XML element
    from lxml import etree
    element = create_notin_element('US')
"""

import re
from typing import Optional, Set
from dataclasses import dataclass


# =============================================================================
# NOTIN Detection Patterns
# =============================================================================

# Values that indicate TIN is not available
NOTIN_VALUES: Set[str] = {
    '',
    'notin',
    'none',
    'n/a',
    'na',
    'not available',
    'not provided',
    'unknown',
    'unavailable',
    '-',
    '0',
    '000000000',
    'null',
}

# Regex patterns for NOTIN-like values
NOTIN_PATTERNS = [
    re.compile(r'^0+$'),  # All zeros
    re.compile(r'^-+$'),  # All dashes
    re.compile(r'^x+$', re.IGNORECASE),  # All X's
    re.compile(r'^\*+$'),  # All asterisks
    re.compile(r'^n\s*/\s*a$', re.IGNORECASE),  # N/A variations
]


# =============================================================================
# NOTIN Data
# =============================================================================

@dataclass
class NOTINData:
    """
    Data for NOTIN XML element generation.

    Attributes:
        value: Always "NOTIN"
        issued_by: Country code for issuedBy attribute
        unknown: Always True for NOTIN
        original_value: Original value that triggered NOTIN detection
        reason: Reason for NOTIN (empty, pattern match, etc.)
    """
    value: str = 'NOTIN'
    issued_by: str = 'XX'
    unknown: bool = True
    original_value: Optional[str] = None
    reason: Optional[str] = None


# =============================================================================
# NOTIN Handler
# =============================================================================

class NOTINHandler:
    """
    Handler for NOTIN (TIN not available) cases.

    Detects when a TIN value indicates unavailability and generates
    appropriate NOTIN data for XML generation.

    Example:
        handler = NOTINHandler()

        # Check various values
        handler.is_notin('')          # True
        handler.is_notin('N/A')       # True
        handler.is_notin('123456789') # False

        # Create NOTIN data
        data = handler.create_notin_data('US')
        # data.value = 'NOTIN'
        # data.issued_by = 'US'
        # data.unknown = True
    """

    def __init__(
        self,
        additional_patterns: Optional[Set[str]] = None,
        strict: bool = False,
    ):
        """
        Initialize NOTIN handler.

        Args:
            additional_patterns: Additional string values to treat as NOTIN
            strict: If True, only match exact NOTIN values (not patterns)
        """
        self.notin_values = NOTIN_VALUES.copy()
        if additional_patterns:
            self.notin_values.update(v.lower() for v in additional_patterns)
        self.strict = strict

    def is_notin(self, value: Optional[str]) -> bool:
        """
        Check if a value indicates TIN is not available.

        Args:
            value: TIN value to check

        Returns:
            True if value indicates NOTIN
        """
        if value is None:
            return True

        value_lower = value.strip().lower()

        # Check exact matches
        if value_lower in self.notin_values:
            return True

        # Check patterns (unless strict mode)
        if not self.strict:
            for pattern in NOTIN_PATTERNS:
                if pattern.match(value_lower):
                    return True

        return False

    def get_notin_reason(self, value: Optional[str]) -> str:
        """
        Get the reason a value was classified as NOTIN.

        Args:
            value: TIN value

        Returns:
            Reason string
        """
        if value is None:
            return "Value is None"

        value_stripped = value.strip()
        value_lower = value_stripped.lower()

        if value_stripped == '':
            return "Empty value"

        if value_lower in self.notin_values:
            return f"Matches NOTIN keyword: '{value_stripped}'"

        for pattern in NOTIN_PATTERNS:
            if pattern.match(value_lower):
                return f"Matches NOTIN pattern: '{value_stripped}'"

        return "Unknown reason"

    def create_notin_data(
        self,
        issued_by: str,
        original_value: Optional[str] = None,
    ) -> NOTINData:
        """
        Create NOTIN data for XML generation.

        Args:
            issued_by: Country code for issuedBy attribute
            original_value: Original TIN value (for tracking)

        Returns:
            NOTINData ready for XML element creation
        """
        reason = self.get_notin_reason(original_value) if original_value else "TIN not provided"

        return NOTINData(
            value='NOTIN',
            issued_by=issued_by.upper() if issued_by else 'XX',
            unknown=True,
            original_value=original_value,
            reason=reason,
        )

    def process_tin(
        self,
        value: Optional[str],
        issued_by: str,
    ) -> tuple[str, bool]:
        """
        Process a TIN value and determine if it's NOTIN.

        Args:
            value: TIN value
            issued_by: Country code

        Returns:
            Tuple of (processed_value, is_unknown)
            - If NOTIN: ('NOTIN', True)
            - If valid: (original_value, False)
        """
        if self.is_notin(value):
            return 'NOTIN', True
        return value.strip(), False


# =============================================================================
# XML Element Creation
# =============================================================================

def create_notin_element(
    issued_by: str,
    namespace: Optional[str] = None,
) -> dict:
    """
    Create NOTIN element data for XML builders.

    Args:
        issued_by: Country code for issuedBy attribute
        namespace: Optional namespace URI

    Returns:
        Dictionary with element data suitable for XML builders:
        {
            'text': 'NOTIN',
            'attrib': {'issuedBy': 'US', 'unknown': 'true'}
        }
    """
    return {
        'text': 'NOTIN',
        'attrib': {
            'issuedBy': issued_by.upper() if issued_by else 'XX',
            'unknown': 'true',
        }
    }


# =============================================================================
# Convenience Functions
# =============================================================================

_default_handler = NOTINHandler()


def is_notin(value: Optional[str]) -> bool:
    """
    Quick check if value indicates NOTIN.

    Args:
        value: TIN value to check

    Returns:
        True if NOTIN
    """
    return _default_handler.is_notin(value)


def process_tin_value(
    value: Optional[str],
    issued_by: str,
) -> tuple[str, bool]:
    """
    Process TIN value, handling NOTIN cases.

    Args:
        value: TIN value
        issued_by: Country code

    Returns:
        Tuple of (value, is_unknown)
    """
    return _default_handler.process_tin(value, issued_by)
