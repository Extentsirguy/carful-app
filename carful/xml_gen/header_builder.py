"""
CARFul - MessageHeader Builder

Builds CARF MessageHeader XML elements with proper namespace handling
and validation. Supports routing metadata, message identification,
and reporting period configuration.

MessageHeader Structure (per OECD CARF XSD v1.5):
    - TransmittingCountry (ISO 3166-1 Alpha-2)
    - ReceivingCountry (ISO 3166-1 Alpha-2)
    - MessageType (always "CARF")
    - Warning (optional, multiple)
    - MessageRefId (UUID)
    - MessageTypeIndic (CARF1/CARF2/CARF3/CARF0)
    - CorrMessageRefId (for corrections)
    - ReportingPeriod (yyyy-MM-dd)
    - Timestamp (ISO 8601 datetime)

Usage:
    from xml_gen.header_builder import HeaderBuilder

    builder = HeaderBuilder(
        transmitting_country='US',
        receiving_country='GB',
        reporting_year=2025,
    )
    header_element = builder.build()
"""

import uuid
from datetime import datetime, date
from typing import List, Optional
from dataclasses import dataclass, field
from lxml import etree

from .namespaces import (
    XMLNamespaceManager,
    get_default_namespace_manager,
    CARF_NS,
)


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class Warning:
    """Warning to include in MessageHeader."""
    code: str
    message: Optional[str] = None


@dataclass
class MessageHeaderData:
    """
    Data container for MessageHeader elements.

    All required fields must be provided. Optional fields can be
    left as None and will be omitted from the XML output.
    """
    # Required routing fields
    transmitting_country: str  # ISO 3166-1 Alpha-2
    receiving_country: str     # ISO 3166-1 Alpha-2

    # Message identification
    message_ref_id: Optional[str] = None  # Auto-generated UUID if None
    message_type: str = "CARF"  # Always CARF for CARF messages

    # Document type indicator
    message_type_indic: Optional[str] = None  # CARF1, CARF2, CARF3, CARF0

    # Correction reference (required when message_type_indic is CARF2)
    corr_message_ref_id: Optional[str] = None

    # Reporting period (last day of reporting year)
    reporting_period: Optional[date] = None  # Auto-set to Dec 31 if None
    reporting_year: int = 2025

    # Timestamp (auto-generated if None)
    timestamp: Optional[datetime] = None

    # Optional warnings
    warnings: List[Warning] = field(default_factory=list)

    def __post_init__(self):
        """Validate and set default values."""
        # Auto-generate message reference ID
        if self.message_ref_id is None:
            self.message_ref_id = str(uuid.uuid4()).upper()

        # Auto-set reporting period to Dec 31 of reporting year
        if self.reporting_period is None:
            self.reporting_period = date(self.reporting_year, 12, 31)

        # Auto-set timestamp to now
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()

        # Validate country codes (basic format check)
        self._validate_country_code(self.transmitting_country, 'transmitting_country')
        self._validate_country_code(self.receiving_country, 'receiving_country')

        # Validate message type indicator
        if self.message_type_indic is not None:
            valid_indicators = {'CARF0', 'CARF1', 'CARF2', 'CARF3'}
            if self.message_type_indic not in valid_indicators:
                raise ValueError(
                    f"Invalid message_type_indic: {self.message_type_indic}. "
                    f"Must be one of {valid_indicators}"
                )

        # Correction reference required for CARF2
        if self.message_type_indic == 'CARF2' and not self.corr_message_ref_id:
            raise ValueError(
                "corr_message_ref_id is required when message_type_indic is CARF2"
            )

    def _validate_country_code(self, code: str, field_name: str) -> None:
        """Validate ISO 3166-1 Alpha-2 country code format."""
        if not code or len(code) != 2 or not code.isalpha():
            raise ValueError(
                f"Invalid {field_name}: '{code}'. Must be 2-letter ISO 3166-1 Alpha-2 code."
            )


# =============================================================================
# Header Builder
# =============================================================================

class HeaderBuilder:
    """
    Builder for CARF MessageHeader XML elements.

    Creates properly structured MessageHeader elements following
    the OECD CARF XSD v1.5 specification.

    Example:
        # Simple usage
        builder = HeaderBuilder(
            transmitting_country='US',
            receiving_country='GB',
            reporting_year=2025,
        )
        header = builder.build()

        # With correction
        builder = HeaderBuilder(
            transmitting_country='US',
            receiving_country='GB',
            reporting_year=2025,
            message_type_indic='CARF2',
            corr_message_ref_id='ORIGINAL-MSG-UUID',
        )
        header = builder.build()

        # From data object
        data = MessageHeaderData(
            transmitting_country='US',
            receiving_country='GB',
            reporting_year=2025,
            warnings=[Warning(code='W001', message='Test warning')],
        )
        builder = HeaderBuilder.from_data(data)
        header = builder.build()
    """

    def __init__(
        self,
        transmitting_country: str,
        receiving_country: str,
        reporting_year: int = 2025,
        message_ref_id: Optional[str] = None,
        message_type_indic: Optional[str] = None,
        corr_message_ref_id: Optional[str] = None,
        timestamp: Optional[datetime] = None,
        warnings: Optional[List[Warning]] = None,
        namespace_manager: Optional[XMLNamespaceManager] = None,
    ):
        """
        Initialize HeaderBuilder with message parameters.

        Args:
            transmitting_country: ISO 3166-1 Alpha-2 code of sending jurisdiction
            receiving_country: ISO 3166-1 Alpha-2 code of receiving jurisdiction
            reporting_year: Tax year being reported (default: 2025)
            message_ref_id: Unique message ID (auto-generated UUID if None)
            message_type_indic: Document type (CARF1=new, CARF2=correction, etc.)
            corr_message_ref_id: Original message ID (required for corrections)
            timestamp: Message timestamp (auto-set to now if None)
            warnings: List of warnings to include
            namespace_manager: Namespace manager for element creation
        """
        self.data = MessageHeaderData(
            transmitting_country=transmitting_country.upper(),
            receiving_country=receiving_country.upper(),
            reporting_year=reporting_year,
            message_ref_id=message_ref_id,
            message_type_indic=message_type_indic,
            corr_message_ref_id=corr_message_ref_id,
            timestamp=timestamp,
            warnings=warnings or [],
        )
        self.nsm = namespace_manager or get_default_namespace_manager()

    @classmethod
    def from_data(
        cls,
        data: MessageHeaderData,
        namespace_manager: Optional[XMLNamespaceManager] = None,
    ) -> 'HeaderBuilder':
        """
        Create HeaderBuilder from MessageHeaderData object.

        Args:
            data: Pre-configured MessageHeaderData
            namespace_manager: Namespace manager for element creation

        Returns:
            Configured HeaderBuilder instance
        """
        builder = cls.__new__(cls)
        builder.data = data
        builder.nsm = namespace_manager or get_default_namespace_manager()
        return builder

    def build(self) -> etree._Element:
        """
        Build the MessageHeader XML element.

        Returns:
            lxml Element containing the complete MessageHeader

        Example:
            header = builder.build()
            # <MessageHeader>
            #   <TransmittingCountry>US</TransmittingCountry>
            #   <ReceivingCountry>GB</ReceivingCountry>
            #   ...
            # </MessageHeader>
        """
        header = self.nsm.create_element('MessageHeader')

        # TransmittingCountry (required)
        self.nsm.create_subelement(
            header, 'TransmittingCountry',
            text=self.data.transmitting_country
        )

        # ReceivingCountry (required)
        self.nsm.create_subelement(
            header, 'ReceivingCountry',
            text=self.data.receiving_country
        )

        # MessageType (required, always "CARF")
        self.nsm.create_subelement(
            header, 'MessageType',
            text=self.data.message_type
        )

        # Warnings (optional, multiple)
        for warning in self.data.warnings:
            self._add_warning(header, warning)

        # MessageRefId (required)
        self.nsm.create_subelement(
            header, 'MessageRefId',
            text=self.data.message_ref_id
        )

        # MessageTypeIndic (optional)
        if self.data.message_type_indic:
            self.nsm.create_subelement(
                header, 'MessageTypeIndic',
                text=self.data.message_type_indic
            )

        # CorrMessageRefId (required for corrections)
        if self.data.corr_message_ref_id:
            self.nsm.create_subelement(
                header, 'CorrMessageRefId',
                text=self.data.corr_message_ref_id
            )

        # ReportingPeriod (required)
        self.nsm.create_subelement(
            header, 'ReportingPeriod',
            text=self.data.reporting_period.isoformat()
        )

        # Timestamp (required)
        self.nsm.create_subelement(
            header, 'Timestamp',
            text=self._format_timestamp(self.data.timestamp)
        )

        return header

    def _add_warning(self, parent: etree._Element, warning: Warning) -> None:
        """Add a Warning element to the header."""
        warning_elem = self.nsm.create_subelement(parent, 'Warning')
        self.nsm.create_subelement(warning_elem, 'WarningCode', text=warning.code)
        if warning.message:
            self.nsm.create_subelement(warning_elem, 'WarningMessage', text=warning.message)

    def _format_timestamp(self, dt: datetime) -> str:
        """Format datetime as ISO 8601 with UTC timezone."""
        # Ensure UTC timezone indicator
        return dt.strftime('%Y-%m-%dT%H:%M:%SZ')

    def with_warning(self, code: str, message: Optional[str] = None) -> 'HeaderBuilder':
        """
        Add a warning to the header (fluent interface).

        Args:
            code: Warning code
            message: Optional warning message

        Returns:
            Self for method chaining
        """
        self.data.warnings.append(Warning(code=code, message=message))
        return self

    def with_correction(self, original_message_ref_id: str) -> 'HeaderBuilder':
        """
        Configure as a correction message (fluent interface).

        Args:
            original_message_ref_id: The MessageRefId of the original message

        Returns:
            Self for method chaining
        """
        self.data.message_type_indic = 'CARF2'
        self.data.corr_message_ref_id = original_message_ref_id
        return self


# =============================================================================
# Factory Functions
# =============================================================================

def create_new_data_header(
    transmitting_country: str,
    receiving_country: str,
    reporting_year: int = 2025,
) -> etree._Element:
    """
    Create a MessageHeader for new data submission (CARF1).

    Args:
        transmitting_country: Sending jurisdiction code
        receiving_country: Receiving jurisdiction code
        reporting_year: Tax year being reported

    Returns:
        MessageHeader element configured for new data
    """
    return HeaderBuilder(
        transmitting_country=transmitting_country,
        receiving_country=receiving_country,
        reporting_year=reporting_year,
        message_type_indic='CARF1',
    ).build()


def create_correction_header(
    transmitting_country: str,
    receiving_country: str,
    original_message_ref_id: str,
    reporting_year: int = 2025,
) -> etree._Element:
    """
    Create a MessageHeader for correction submission (CARF2).

    Args:
        transmitting_country: Sending jurisdiction code
        receiving_country: Receiving jurisdiction code
        original_message_ref_id: MessageRefId of message being corrected
        reporting_year: Tax year being reported

    Returns:
        MessageHeader element configured for correction
    """
    return HeaderBuilder(
        transmitting_country=transmitting_country,
        receiving_country=receiving_country,
        reporting_year=reporting_year,
        message_type_indic='CARF2',
        corr_message_ref_id=original_message_ref_id,
    ).build()


def create_deletion_header(
    transmitting_country: str,
    receiving_country: str,
    original_message_ref_id: str,
    reporting_year: int = 2025,
) -> etree._Element:
    """
    Create a MessageHeader for deletion submission (CARF3).

    Args:
        transmitting_country: Sending jurisdiction code
        receiving_country: Receiving jurisdiction code
        original_message_ref_id: MessageRefId of message being deleted
        reporting_year: Tax year being reported

    Returns:
        MessageHeader element configured for deletion
    """
    return HeaderBuilder(
        transmitting_country=transmitting_country,
        receiving_country=receiving_country,
        reporting_year=reporting_year,
        message_type_indic='CARF3',
        corr_message_ref_id=original_message_ref_id,
    ).build()
