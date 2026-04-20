"""
CARFul - CARFBody Data Models

This module defines the CARFBody structure and its components for CARF XML messages.
The CARFBody contains the ReportingGroup with RCASP and CryptoUser information.

Reference: OECD CARF XML Schema v2.0 (July 2025) - Section IV
"""

from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List, Annotated, Union
from pydantic import BaseModel, Field, field_validator, model_validator
import uuid
import sys
from pathlib import Path

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from validators.country_codes import is_valid_country_code, validate_country_code, get_country_name
from enumerations import (
    DocTypeIndicator,
    NexusType,
    TransactionCategory,
    ExchangeType,
    TransferInType,
    TransferOutType,
    is_valid_transaction_type,
    get_transaction_category,
)


# =============================================================================
# Document Specification (DocSpec) - Used for corrections
# =============================================================================

class DocSpec(BaseModel):
    """
    Document Specification for tracking corrections and deletions.

    Used to identify records and facilitate corrections/deletions
    of previously submitted data.
    """

    doc_type_indic: Annotated[
        DocTypeIndicator,
        Field(
            default=DocTypeIndicator.OECD1,
            description="OECD1 (new), OECD2 (correction), OECD3 (deletion)"
        )
    ] = DocTypeIndicator.OECD1

    doc_ref_id: Annotated[
        str,
        Field(
            min_length=1,
            max_length=200,
            description="Unique document reference ID within the message"
        )
    ]

    corr_doc_ref_id: Optional[str] = Field(
        default=None,
        description="Reference to the document being corrected (required for OECD2/OECD3)"
    )

    class Config:
        use_enum_values = True

    @model_validator(mode='after')
    def validate_correction_ref(self) -> 'DocSpec':
        """Corrections and deletions must reference the original document."""
        if self.doc_type_indic in [DocTypeIndicator.OECD2, DocTypeIndicator.OECD3]:
            if not self.corr_doc_ref_id:
                raise ValueError(
                    f"corr_doc_ref_id is required for {self.doc_type_indic} (correction/deletion)"
                )
        return self

    @classmethod
    def generate_doc_ref_id(cls, prefix: str = "DOC") -> str:
        """Generate a unique document reference ID."""
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        unique_id = uuid.uuid4().hex[:8]
        return f"{prefix}_{timestamp}_{unique_id}"

    @classmethod
    def new(cls, prefix: str = "DOC") -> 'DocSpec':
        """Create a new document specification."""
        return cls(
            doc_type_indic=DocTypeIndicator.OECD1,
            doc_ref_id=cls.generate_doc_ref_id(prefix),
        )

    @classmethod
    def correction(cls, original_ref_id: str, prefix: str = "DOC") -> 'DocSpec':
        """Create a correction document specification."""
        return cls(
            doc_type_indic=DocTypeIndicator.OECD2,
            doc_ref_id=cls.generate_doc_ref_id(prefix),
            corr_doc_ref_id=original_ref_id,
        )

    @classmethod
    def deletion(cls, original_ref_id: str, prefix: str = "DOC") -> 'DocSpec':
        """Create a deletion document specification."""
        return cls(
            doc_type_indic=DocTypeIndicator.OECD3,
            doc_ref_id=cls.generate_doc_ref_id(prefix),
            corr_doc_ref_id=original_ref_id,
        )


# =============================================================================
# Address Structure
# =============================================================================

class Address(BaseModel):
    """
    Address structure for RCASP and CryptoUser.

    Supports both structured and free-form address formats.
    """

    address_type: str = Field(
        default="OECD303",
        description="Address type code (OECD303 = business, OECD301 = residential)"
    )

    street: Optional[str] = Field(default=None, max_length=200)
    building_identifier: Optional[str] = Field(default=None, max_length=50)
    suite_identifier: Optional[str] = Field(default=None, max_length=50)
    floor_identifier: Optional[str] = Field(default=None, max_length=50)
    post_code: Optional[str] = Field(default=None, max_length=20)
    city: Optional[str] = Field(default=None, max_length=100)
    country_subentity: Optional[str] = Field(default=None, max_length=100, description="State/Province")

    country_code: Annotated[
        str,
        Field(
            min_length=2,
            max_length=2,
            description="ISO 3166-1 Alpha-2 country code"
        )
    ]

    # Free-form address (alternative to structured)
    address_free: Optional[str] = Field(
        default=None,
        max_length=750,
        description="Free-form address text"
    )

    @field_validator('country_code', mode='before')
    @classmethod
    def validate_country(cls, v: str) -> str:
        """Validate country code."""
        if not v:
            raise ValueError("Country code is required")
        normalized = v.upper().strip()
        is_valid, corrected, error = validate_country_code(normalized)
        if not is_valid:
            if corrected:
                raise ValueError(f"{error} Use '{corrected}' instead.")
            raise ValueError(error)
        return corrected or normalized

    def get_country_name(self) -> str:
        """Get full country name."""
        return get_country_name(self.country_code) or "Unknown"

    def to_single_line(self) -> str:
        """Convert to single-line address string."""
        if self.address_free:
            return self.address_free

        parts = []
        if self.building_identifier:
            parts.append(self.building_identifier)
        if self.street:
            parts.append(self.street)
        if self.suite_identifier:
            parts.append(f"Suite {self.suite_identifier}")
        if self.city:
            city_part = self.city
            if self.country_subentity:
                city_part += f", {self.country_subentity}"
            if self.post_code:
                city_part += f" {self.post_code}"
            parts.append(city_part)
        parts.append(self.get_country_name())

        return ", ".join(parts)


# =============================================================================
# TIN (Tax Identification Number)
# =============================================================================

class TIN(BaseModel):
    """
    Tax Identification Number structure.

    Supports both known TINs and 'NOTIN' cases where TIN is unavailable.
    """

    value: Annotated[
        str,
        Field(
            min_length=1,
            max_length=200,
            description="TIN value or 'NOTIN'"
        )
    ]

    issued_by: Optional[str] = Field(
        default=None,
        min_length=2,
        max_length=2,
        description="Country that issued the TIN"
    )

    tin_type: Optional[str] = Field(
        default=None,
        description="Type of TIN (jurisdiction-specific)"
    )

    is_unknown: bool = Field(
        default=False,
        description="True if TIN is unavailable (value should be 'NOTIN')"
    )

    @field_validator('issued_by', mode='before')
    @classmethod
    def validate_issuer(cls, v: Optional[str]) -> Optional[str]:
        """Validate issuing country code."""
        if not v:
            return None
        normalized = v.upper().strip()
        is_valid, corrected, error = validate_country_code(normalized)
        if not is_valid:
            if corrected:
                raise ValueError(f"{error} Use '{corrected}' instead.")
            raise ValueError(error)
        return corrected or normalized

    @model_validator(mode='after')
    def validate_notin(self) -> 'TIN':
        """Validate NOTIN consistency."""
        if self.value.upper() == "NOTIN":
            object.__setattr__(self, 'is_unknown', True)
        elif self.is_unknown and self.value.upper() != "NOTIN":
            raise ValueError("If is_unknown is True, value must be 'NOTIN'")
        return self

    @classmethod
    def known(cls, value: str, issued_by: str, tin_type: Optional[str] = None) -> 'TIN':
        """Create a known TIN."""
        return cls(value=value, issued_by=issued_by, tin_type=tin_type, is_unknown=False)

    @classmethod
    def unknown(cls, issued_by: Optional[str] = None) -> 'TIN':
        """Create an unknown TIN (NOTIN)."""
        return cls(value="NOTIN", issued_by=issued_by, is_unknown=True)


# =============================================================================
# Name Structures
# =============================================================================

class IndividualName(BaseModel):
    """Name structure for individual persons."""

    first_name: Annotated[str, Field(min_length=1, max_length=200)]
    middle_name: Optional[str] = Field(default=None, max_length=200)
    last_name: Annotated[str, Field(min_length=1, max_length=200)]
    name_prefix: Optional[str] = Field(default=None, max_length=50, description="Mr., Mrs., Dr., etc.")
    name_suffix: Optional[str] = Field(default=None, max_length=50, description="Jr., III, etc.")

    def full_name(self) -> str:
        """Get full name as single string."""
        parts = []
        if self.name_prefix:
            parts.append(self.name_prefix)
        parts.append(self.first_name)
        if self.middle_name:
            parts.append(self.middle_name)
        parts.append(self.last_name)
        if self.name_suffix:
            parts.append(self.name_suffix)
        return " ".join(parts)


class EntityName(BaseModel):
    """Name structure for organizations/entities."""

    legal_name: Annotated[str, Field(min_length=1, max_length=500)]
    trading_name: Optional[str] = Field(default=None, max_length=500, description="DBA name")

    def display_name(self) -> str:
        """Get display name."""
        if self.trading_name:
            return f"{self.legal_name} (DBA: {self.trading_name})"
        return self.legal_name


# =============================================================================
# Birth Information (for Individuals)
# =============================================================================

class BirthInfo(BaseModel):
    """Birth information for individual identification."""

    birth_date: Optional[date] = Field(default=None)
    birth_city: Optional[str] = Field(default=None, max_length=100)
    birth_country: Optional[str] = Field(default=None, min_length=2, max_length=2)

    @field_validator('birth_country', mode='before')
    @classmethod
    def validate_country(cls, v: Optional[str]) -> Optional[str]:
        """Validate birth country code."""
        if not v:
            return None
        normalized = v.upper().strip()
        is_valid, corrected, error = validate_country_code(normalized)
        if not is_valid:
            if corrected:
                return corrected
            raise ValueError(error)
        return corrected or normalized


# =============================================================================
# RCASP (Reporting Crypto-Asset Service Provider)
# =============================================================================

class RCASP(BaseModel):
    """
    Reporting Crypto-Asset Service Provider.

    The entity obligated to report under CARF.
    """

    doc_spec: DocSpec = Field(default_factory=lambda: DocSpec.new("RCASP"))

    # Identity
    name: EntityName
    tin: Optional[TIN] = Field(default=None)

    # Address
    address: Address

    # Nexus
    nexus_type: Annotated[
        NexusType,
        Field(description="Basis for reporting obligation")
    ]

    # Is this an individual RCASP? (rare but possible)
    is_individual: bool = Field(default=False)
    individual_name: Optional[IndividualName] = Field(default=None)

    class Config:
        use_enum_values = True

    @model_validator(mode='after')
    def validate_individual(self) -> 'RCASP':
        """Validate individual RCASP has name."""
        if self.is_individual and not self.individual_name:
            raise ValueError("Individual RCASP requires individual_name")
        return self

    def get_display_name(self) -> str:
        """Get display name for the RCASP."""
        if self.is_individual and self.individual_name:
            return self.individual_name.full_name()
        return self.name.display_name()


# =============================================================================
# Relevant Transaction
# =============================================================================

class RelevantTransaction(BaseModel):
    """
    A reportable crypto-asset transaction.

    Represents exchange, transfer, or retail payment transactions.
    """

    # Transaction Classification
    transaction_category: TransactionCategory
    transaction_type: str = Field(description="CARF code (CARF401-606)")

    # Asset Information
    asset_type: Annotated[str, Field(min_length=1, max_length=50, description="Crypto asset (BTC, ETH, etc.)")]
    asset_name: Optional[str] = Field(default=None, max_length=200)

    # Amounts (using Decimal for precision)
    amount: Decimal = Field(description="Quantity of crypto asset")
    amount_fiat: Optional[Decimal] = Field(default=None, description="Fiat equivalent value")
    fiat_currency: Optional[str] = Field(default=None, max_length=3, description="ISO 4217 currency code")

    # For exchanges
    acquired_asset_type: Optional[str] = Field(default=None, max_length=50)
    acquired_amount: Optional[Decimal] = Field(default=None)
    disposed_asset_type: Optional[str] = Field(default=None, max_length=50)
    disposed_amount: Optional[Decimal] = Field(default=None)

    # Transaction Details
    transaction_id: Optional[str] = Field(default=None, max_length=200, description="Blockchain/exchange tx ID")
    timestamp: datetime

    # Aggregation
    is_aggregated: bool = Field(default=False)
    aggregation_count: int = Field(default=1, ge=1)

    # Source tracking
    source_row: Optional[int] = Field(default=None, description="Original CSV row number")
    source_file: Optional[str] = Field(default=None)

    class Config:
        use_enum_values = True

    @field_validator('transaction_type', mode='before')
    @classmethod
    def validate_transaction_type(cls, v: str) -> str:
        """Validate CARF transaction type code."""
        if not is_valid_transaction_type(v):
            raise ValueError(f"Invalid transaction type: {v}")
        return v

    @model_validator(mode='after')
    def validate_category_matches_type(self) -> 'RelevantTransaction':
        """Ensure transaction type matches category."""
        expected_category = get_transaction_category(self.transaction_type)
        if expected_category:
            # Handle both enum and string values (due to use_enum_values=True)
            current_cat = (
                self.transaction_category.value
                if hasattr(self.transaction_category, 'value')
                else self.transaction_category
            )
            expected_cat = expected_category.value
            if expected_cat != current_cat:
                raise ValueError(
                    f"Transaction type {self.transaction_type} should have category "
                    f"{expected_cat}, not {current_cat}"
                )
        return self


# =============================================================================
# CryptoUser (Reportable User)
# =============================================================================

class CryptoUser(BaseModel):
    """
    A reportable crypto user/account holder.

    Can be an individual or entity with associated transactions.
    """

    doc_spec: DocSpec = Field(default_factory=lambda: DocSpec.new("USER"))

    # User Type
    is_individual: bool = Field(default=True)

    # Identity (one of these required based on is_individual)
    individual_name: Optional[IndividualName] = Field(default=None)
    entity_name: Optional[EntityName] = Field(default=None)

    # Tax Information
    tin: Optional[TIN] = Field(default=None)
    tax_residency: Annotated[
        str,
        Field(min_length=2, max_length=2, description="Primary tax residency country code")
    ]

    # Address
    address: Optional[Address] = Field(default=None)

    # Birth Information (for individuals)
    birth_info: Optional[BirthInfo] = Field(default=None)

    # Account Information
    account_number: Optional[str] = Field(default=None, max_length=200)
    account_number_type: Optional[str] = Field(default=None, max_length=50)

    # Controlling Persons (for entities)
    controlling_persons: List['ControllingPerson'] = Field(default_factory=list)

    # Transactions
    transactions: List[RelevantTransaction] = Field(default_factory=list)

    # Source tracking
    source_row: Optional[int] = Field(default=None)

    class Config:
        use_enum_values = True

    @field_validator('tax_residency', mode='before')
    @classmethod
    def validate_tax_residency(cls, v: str) -> str:
        """Validate tax residency country code."""
        if not v:
            raise ValueError("Tax residency is required")
        normalized = v.upper().strip()
        is_valid, corrected, error = validate_country_code(normalized)
        if not is_valid:
            if corrected:
                raise ValueError(f"{error} Use '{corrected}' instead.")
            raise ValueError(error)
        return corrected or normalized

    @model_validator(mode='after')
    def validate_identity(self) -> 'CryptoUser':
        """Validate that appropriate name is provided."""
        if self.is_individual:
            if not self.individual_name:
                raise ValueError("Individual user requires individual_name")
        else:
            if not self.entity_name:
                raise ValueError("Entity user requires entity_name")
        return self

    def get_display_name(self) -> str:
        """Get display name for the user."""
        if self.is_individual and self.individual_name:
            return self.individual_name.full_name()
        elif self.entity_name:
            return self.entity_name.display_name()
        return "Unknown"

    def add_transaction(self, transaction: RelevantTransaction) -> None:
        """Add a transaction to this user."""
        self.transactions.append(transaction)

    def transaction_count(self) -> int:
        """Get total transaction count."""
        return len(self.transactions)

    def total_by_asset(self) -> dict[str, Decimal]:
        """Calculate totals by asset type."""
        totals: dict[str, Decimal] = {}
        for tx in self.transactions:
            totals[tx.asset_type] = totals.get(tx.asset_type, Decimal(0)) + tx.amount
        return totals


# =============================================================================
# Controlling Person (for Entity Users)
# =============================================================================

class ControllingPerson(BaseModel):
    """
    Controlling person of an entity CryptoUser.

    Required for entity users to identify beneficial owners.
    """

    name: IndividualName
    tin: Optional[TIN] = Field(default=None)
    tax_residency: Annotated[str, Field(min_length=2, max_length=2)]
    address: Optional[Address] = Field(default=None)
    birth_info: Optional[BirthInfo] = Field(default=None)
    control_type: Optional[str] = Field(default=None, description="Type of control (beneficial owner, director, etc.)")

    @field_validator('tax_residency', mode='before')
    @classmethod
    def validate_tax_residency(cls, v: str) -> str:
        """Validate tax residency country code."""
        if not v:
            raise ValueError("Tax residency is required")
        normalized = v.upper().strip()
        is_valid, corrected, error = validate_country_code(normalized)
        if not is_valid:
            raise ValueError(error)
        return corrected or normalized


# =============================================================================
# ReportingGroup - Container for RCASP and Users
# =============================================================================

class ReportingGroup(BaseModel):
    """
    Reporting Group containing RCASP and associated CryptoUsers.

    This is the main container within CARFBody.
    """

    rcasp: RCASP
    crypto_users: List[CryptoUser] = Field(default_factory=list)

    # Optional Sponsor (for sponsored RCASPs)
    sponsor: Optional[RCASP] = Field(default=None)

    def add_user(self, user: CryptoUser) -> None:
        """Add a crypto user to this reporting group."""
        self.crypto_users.append(user)

    def user_count(self) -> int:
        """Get count of crypto users."""
        return len(self.crypto_users)

    def total_transaction_count(self) -> int:
        """Get total transaction count across all users."""
        return sum(user.transaction_count() for user in self.crypto_users)


# =============================================================================
# CARFBody - Main Body Structure
# =============================================================================

class CARFBody(BaseModel):
    """
    CARF Message Body.

    Contains the ReportingGroup with RCASP and CryptoUser information.
    This is the main data payload of a CARF message.
    """

    reporting_group: ReportingGroup

    def get_rcasp(self) -> RCASP:
        """Get the RCASP from this body."""
        return self.reporting_group.rcasp

    def get_users(self) -> List[CryptoUser]:
        """Get all crypto users."""
        return self.reporting_group.crypto_users

    def add_user(self, user: CryptoUser) -> None:
        """Add a user to the reporting group."""
        self.reporting_group.add_user(user)

    def summary(self) -> dict:
        """Get summary statistics for this body."""
        users = self.get_users()
        total_tx = sum(u.transaction_count() for u in users)

        return {
            "rcasp_name": self.get_rcasp().get_display_name(),
            "rcasp_country": self.get_rcasp().address.country_code,
            "user_count": len(users),
            "transaction_count": total_tx,
            "has_sponsor": self.reporting_group.sponsor is not None,
        }


# Update forward reference
CryptoUser.model_rebuild()


if __name__ == "__main__":
    from decimal import Decimal

    # Example: Create a complete CARF body
    rcasp = RCASP(
        name=EntityName(legal_name="CryptoExchange Inc."),
        address=Address(
            street="123 Blockchain Street",
            city="New York",
            country_subentity="NY",
            post_code="10001",
            country_code="US",
        ),
        tin=TIN.known("12-3456789", "US", "EIN"),
        nexus_type=NexusType.CARF801,
    )

    user = CryptoUser(
        individual_name=IndividualName(first_name="John", last_name="Doe"),
        tax_residency="US",
        tin=TIN.known("123-45-6789", "US", "SSN"),
        address=Address(
            street="456 Crypto Lane",
            city="Los Angeles",
            country_subentity="CA",
            post_code="90001",
            country_code="US",
        ),
    )

    user.add_transaction(RelevantTransaction(
        transaction_category=TransactionCategory.TRANSFER_IN,
        transaction_type="CARF501",
        asset_type="BTC",
        amount=Decimal("0.5"),
        amount_fiat=Decimal("25000.00"),
        fiat_currency="USD",
        timestamp=datetime(2025, 6, 15, 10, 30, 0),
    ))

    body = CARFBody(
        reporting_group=ReportingGroup(rcasp=rcasp, crypto_users=[user])
    )

    print("CARFBody Summary:")
    for k, v in body.summary().items():
        print(f"  {k}: {v}")
