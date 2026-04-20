"""
CARFul - MessageHeader Data Model

This module defines the MessageHeader structure for CARF XML messages.
The MessageHeader contains metadata about the CARF submission including
sending/receiving jurisdictions, message type, and timestamps.

Reference: OECD CARF XML Schema v2.0 (July 2025) - Section I
"""

from datetime import datetime, date
from typing import Optional, Annotated
from pydantic import BaseModel, Field, field_validator, model_validator
import uuid
import sys
from pathlib import Path

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from validators.country_codes import is_valid_country_code, validate_country_code, get_country_name
from enumerations import MessageTypeIndicator


class MessageHeader(BaseModel):
    """
    CARF Message Header structure.

    Contains metadata for a CARF XML message including identification
    of sending/receiving tax authorities, message type, and timestamps.

    Attributes:
        sending_comp_auth: ISO 3166-1 Alpha-2 code of sending jurisdiction
        receiving_comp_auth: ISO 3166-1 Alpha-2 code of receiving jurisdiction
        message_type: Always "CARF" for CARF messages
        message_type_indic: CARF701 (new), CARF702 (correction), CARF703 (nil)
        message_ref_id: Unique message reference identifier
        reporting_period_start: Start of reporting period (YYYY-MM-DD)
        reporting_period_end: End of reporting period (YYYY-MM-DD)
        timestamp: Message creation timestamp (ISO 8601)
    """

    # Sending/Receiving Jurisdictions
    sending_comp_auth: Annotated[
        str,
        Field(
            min_length=2,
            max_length=2,
            description="ISO 3166-1 Alpha-2 country code of sending Competent Authority"
        )
    ]

    receiving_comp_auth: Annotated[
        str,
        Field(
            min_length=2,
            max_length=2,
            description="ISO 3166-1 Alpha-2 country code of receiving Competent Authority"
        )
    ]

    # Message Identification
    message_type: Annotated[
        str,
        Field(
            default="CARF",
            description="Message type - always 'CARF' for CARF messages"
        )
    ] = "CARF"

    message_type_indic: Annotated[
        MessageTypeIndicator,
        Field(
            description="Message type indicator: CARF701 (new), CARF702 (correction), CARF703 (nil)"
        )
    ]

    message_ref_id: Annotated[
        str,
        Field(
            min_length=1,
            max_length=200,
            description="Unique message reference identifier"
        )
    ]

    # Reporting Period
    reporting_period_start: Annotated[
        date,
        Field(description="Start date of reporting period")
    ]

    reporting_period_end: Annotated[
        date,
        Field(description="End date of reporting period")
    ]

    # Timestamp
    timestamp: Annotated[
        datetime,
        Field(
            default_factory=datetime.utcnow,
            description="Message creation timestamp (UTC)"
        )
    ]

    # Optional: Contact information
    contact_name: Optional[str] = Field(default=None, description="Contact person name")
    contact_email: Optional[str] = Field(default=None, description="Contact email address")
    contact_phone: Optional[str] = Field(default=None, description="Contact phone number")

    class Config:
        """Pydantic model configuration."""
        str_strip_whitespace = True
        validate_assignment = True
        use_enum_values = True

    @field_validator('sending_comp_auth', 'receiving_comp_auth', mode='before')
    @classmethod
    def validate_country_code(cls, v: str) -> str:
        """Validate and normalize country codes."""
        if not v:
            raise ValueError("Country code is required")

        normalized = v.upper().strip()

        # Check for valid code
        is_valid, corrected, error = validate_country_code(normalized)

        if not is_valid:
            if corrected:
                raise ValueError(f"{error} Use '{corrected}' instead.")
            raise ValueError(error)

        return corrected or normalized

    @field_validator('message_type', mode='before')
    @classmethod
    def validate_message_type(cls, v: str) -> str:
        """Ensure message type is always 'CARF'."""
        if v and v.upper() != "CARF":
            raise ValueError("Message type must be 'CARF'")
        return "CARF"

    @model_validator(mode='after')
    def validate_reporting_period(self) -> 'MessageHeader':
        """Validate that reporting period end is after start."""
        if self.reporting_period_end < self.reporting_period_start:
            raise ValueError(
                f"Reporting period end ({self.reporting_period_end}) must be "
                f"after start ({self.reporting_period_start})"
            )
        return self

    @classmethod
    def generate_message_ref_id(cls, prefix: str = "CARF") -> str:
        """
        Generate a unique message reference ID.

        Format: {prefix}_{timestamp}_{uuid}
        Example: CARF_20260201_a1b2c3d4

        Args:
            prefix: Prefix for the message ID

        Returns:
            Unique message reference ID
        """
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        unique_id = uuid.uuid4().hex[:8]
        return f"{prefix}_{timestamp}_{unique_id}"

    def get_sending_country_name(self) -> str:
        """Get the full name of the sending country."""
        return get_country_name(self.sending_comp_auth) or "Unknown"

    def get_receiving_country_name(self) -> str:
        """Get the full name of the receiving country."""
        return get_country_name(self.receiving_comp_auth) or "Unknown"

    def to_xml_dict(self) -> dict:
        """
        Convert to dictionary suitable for XML generation.

        Returns:
            Dictionary with XML element names as keys
        """
        return {
            "SendingCompAuth": self.sending_comp_auth,
            "ReceivingCompAuth": self.receiving_comp_auth,
            "MessageType": self.message_type,
            "MessageTypeIndic": self.message_type_indic,
            "MessageRefId": self.message_ref_id,
            "ReportingPeriod": {
                "Start": self.reporting_period_start.isoformat(),
                "End": self.reporting_period_end.isoformat(),
            },
            "Timestamp": self.timestamp.isoformat() + "Z",
        }

    def __str__(self) -> str:
        """Human-readable string representation."""
        return (
            f"MessageHeader("
            f"{self.sending_comp_auth}→{self.receiving_comp_auth}, "
            f"{self.message_type_indic}, "
            f"ref={self.message_ref_id[:20]}...)"
        )


class MessageHeaderBuilder:
    """
    Builder pattern for creating MessageHeader instances.

    Provides a fluent interface for constructing message headers
    with sensible defaults.
    """

    def __init__(self):
        self._sending_comp_auth: Optional[str] = None
        self._receiving_comp_auth: Optional[str] = None
        self._message_type_indic: MessageTypeIndicator = MessageTypeIndicator.CARF701
        self._message_ref_id: Optional[str] = None
        self._reporting_period_start: Optional[date] = None
        self._reporting_period_end: Optional[date] = None
        self._timestamp: Optional[datetime] = None
        self._contact_name: Optional[str] = None
        self._contact_email: Optional[str] = None

    def from_jurisdiction(self, country_code: str) -> 'MessageHeaderBuilder':
        """Set the sending jurisdiction."""
        self._sending_comp_auth = country_code
        return self

    def to_jurisdiction(self, country_code: str) -> 'MessageHeaderBuilder':
        """Set the receiving jurisdiction."""
        self._receiving_comp_auth = country_code
        return self

    def as_new_submission(self) -> 'MessageHeaderBuilder':
        """Mark as new data submission (CARF701)."""
        self._message_type_indic = MessageTypeIndicator.CARF701
        return self

    def as_correction(self) -> 'MessageHeaderBuilder':
        """Mark as correction/deletion (CARF702)."""
        self._message_type_indic = MessageTypeIndicator.CARF702
        return self

    def as_nil_report(self) -> 'MessageHeaderBuilder':
        """Mark as nil report (CARF703)."""
        self._message_type_indic = MessageTypeIndicator.CARF703
        return self

    def for_year(self, year: int) -> 'MessageHeaderBuilder':
        """Set reporting period to full calendar year."""
        self._reporting_period_start = date(year, 1, 1)
        self._reporting_period_end = date(year, 12, 31)
        return self

    def for_period(self, start: date, end: date) -> 'MessageHeaderBuilder':
        """Set custom reporting period."""
        self._reporting_period_start = start
        self._reporting_period_end = end
        return self

    def with_reference(self, ref_id: str) -> 'MessageHeaderBuilder':
        """Set custom message reference ID."""
        self._message_ref_id = ref_id
        return self

    def with_contact(self, name: str, email: Optional[str] = None) -> 'MessageHeaderBuilder':
        """Set contact information."""
        self._contact_name = name
        self._contact_email = email
        return self

    def build(self) -> MessageHeader:
        """
        Build and return the MessageHeader.

        Raises:
            ValueError: If required fields are missing
        """
        if not self._sending_comp_auth:
            raise ValueError("Sending jurisdiction is required")
        if not self._receiving_comp_auth:
            raise ValueError("Receiving jurisdiction is required")
        if not self._reporting_period_start or not self._reporting_period_end:
            raise ValueError("Reporting period is required")

        return MessageHeader(
            sending_comp_auth=self._sending_comp_auth,
            receiving_comp_auth=self._receiving_comp_auth,
            message_type_indic=self._message_type_indic,
            message_ref_id=self._message_ref_id or MessageHeader.generate_message_ref_id(),
            reporting_period_start=self._reporting_period_start,
            reporting_period_end=self._reporting_period_end,
            timestamp=self._timestamp or datetime.utcnow(),
            contact_name=self._contact_name,
            contact_email=self._contact_email,
        )


# Convenience function
def create_header(
    sending: str,
    receiving: str,
    year: int,
    message_type: MessageTypeIndicator = MessageTypeIndicator.CARF701,
) -> MessageHeader:
    """
    Quick helper to create a standard MessageHeader.

    Args:
        sending: Sending jurisdiction country code
        receiving: Receiving jurisdiction country code
        year: Reporting year
        message_type: Message type indicator

    Returns:
        Configured MessageHeader instance
    """
    return (
        MessageHeaderBuilder()
        .from_jurisdiction(sending)
        .to_jurisdiction(receiving)
        .for_year(year)
        .as_new_submission() if message_type == MessageTypeIndicator.CARF701 else
        MessageHeaderBuilder()
        .from_jurisdiction(sending)
        .to_jurisdiction(receiving)
        .for_year(year)
    ).build()


if __name__ == "__main__":
    # Example usage
    header = (
        MessageHeaderBuilder()
        .from_jurisdiction("US")
        .to_jurisdiction("GB")
        .for_year(2025)
        .as_new_submission()
        .with_contact("John Doe", "john@example.com")
        .build()
    )

    print("Created MessageHeader:")
    print(f"  From: {header.get_sending_country_name()} ({header.sending_comp_auth})")
    print(f"  To: {header.get_receiving_country_name()} ({header.receiving_comp_auth})")
    print(f"  Type: {header.message_type_indic}")
    print(f"  Period: {header.reporting_period_start} to {header.reporting_period_end}")
    print(f"  Ref ID: {header.message_ref_id}")
    print(f"\nXML Dict: {header.to_xml_dict()}")
