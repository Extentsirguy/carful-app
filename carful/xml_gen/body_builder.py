"""
CARFul - CARFBody Builder

Builds CARF Body XML elements with nested ReportingGroup structure.
Supports RCASP (Reporting Crypto-Asset Service Provider) information
and address elements.

CARFBody Structure (per OECD CARF XSD v1.5):
    - CARFBody
      - ReportingGroup
        - RCASP
          - DocSpec
          - Name
          - TIN (optional, multiple)
          - Address
        - CryptoUser (1..n) - see user_builder.py

Usage:
    from xml_gen.body_builder import BodyBuilder, RCASPData, AddressData

    rcasp = RCASPData(
        name='Crypto Exchange Inc.',
        tin='12-3456789',
        tin_country='US',
        address=AddressData(
            street='123 Blockchain Ave',
            city='San Francisco',
            country='US',
            post_code='94105',
        ),
    )
    builder = BodyBuilder(rcasp=rcasp)

    # Add users via user_builder
    body_element = builder.build()
"""

import uuid
from typing import List, Optional
from dataclasses import dataclass, field
from lxml import etree

from .namespaces import (
    XMLNamespaceManager,
    get_default_namespace_manager,
)


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class AddressData:
    """
    Address information for RCASP or user.

    Per OECD CARF XSD, City and Country are required.
    Other fields are optional.
    """
    # Required fields
    city: str
    country: str  # ISO 3166-1 Alpha-2

    # Optional fields
    street: Optional[str] = None
    building_identifier: Optional[str] = None
    suite_identifier: Optional[str] = None
    floor_identifier: Optional[str] = None
    district_name: Optional[str] = None
    pob: Optional[str] = None  # Post Office Box
    post_code: Optional[str] = None
    country_subentity: Optional[str] = None  # State/Province

    def __post_init__(self):
        """Validate required fields."""
        if not self.city:
            raise ValueError("city is required for Address")
        if not self.country or len(self.country) != 2:
            raise ValueError("country must be a 2-letter ISO 3166-1 Alpha-2 code")
        self.country = self.country.upper()


@dataclass
class TINData:
    """
    Tax Identification Number with jurisdiction.

    Supports both known TINs and NOTIN cases where TIN is unavailable.
    """
    value: str
    issued_by: str  # ISO 3166-1 Alpha-2 country code
    unknown: bool = False  # True for NOTIN cases

    def __post_init__(self):
        """Validate TIN data."""
        if not self.issued_by or len(self.issued_by) != 2:
            raise ValueError("issued_by must be a 2-letter ISO country code")
        self.issued_by = self.issued_by.upper()

        # For NOTIN cases, value should be "NOTIN"
        if self.unknown and self.value != 'NOTIN':
            self.value = 'NOTIN'

    @classmethod
    def notin(cls, issued_by: str) -> 'TINData':
        """Create a NOTIN (TIN unavailable) entry."""
        return cls(value='NOTIN', issued_by=issued_by, unknown=True)


@dataclass
class DocSpecData:
    """
    Document specification for tracking records.

    Used for identifying records for corrections and deletions.
    """
    doc_type_indic: str = 'CARF1'  # CARF1=new, CARF2=correction, CARF3=delete
    doc_ref_id: Optional[str] = None  # Auto-generated if None
    corr_message_ref_id: Optional[str] = None  # For corrections
    corr_doc_ref_id: Optional[str] = None  # For corrections

    def __post_init__(self):
        """Validate and auto-generate doc_ref_id."""
        if self.doc_ref_id is None:
            self.doc_ref_id = f"DOC-{uuid.uuid4().hex[:12].upper()}"

        valid_types = {'CARF0', 'CARF1', 'CARF2', 'CARF3'}
        if self.doc_type_indic not in valid_types:
            raise ValueError(f"doc_type_indic must be one of {valid_types}")


@dataclass
class RCASPData:
    """
    Reporting Crypto-Asset Service Provider data.

    Required information about the entity submitting the CARF report.
    """
    name: str
    address: AddressData

    # Optional fields
    tins: List[TINData] = field(default_factory=list)
    legal_type: Optional[str] = None  # e.g., "LLC", "Corp"
    doc_spec: Optional[DocSpecData] = None

    # Convenience for single TIN
    tin: Optional[str] = None
    tin_country: Optional[str] = None

    def __post_init__(self):
        """Process convenience TIN fields."""
        if self.doc_spec is None:
            self.doc_spec = DocSpecData()

        # Add single TIN to list if provided
        if self.tin and self.tin_country:
            self.tins.append(TINData(value=self.tin, issued_by=self.tin_country))


# =============================================================================
# Body Builder
# =============================================================================

class BodyBuilder:
    """
    Builder for CARFBody XML elements.

    Creates the CARFBody > ReportingGroup > RCASP structure.
    CryptoUser elements are added separately via add_user() or
    by passing user elements to build().

    Example:
        builder = BodyBuilder(rcasp=rcasp_data)

        # Build body with user elements
        user_elements = [user_builder.build() for user in users]
        body = builder.build(user_elements)

        # Or use streaming approach
        with writer.element('CARFBody'):
            with writer.element('ReportingGroup'):
                writer.write_element(builder.build_rcasp())
                for user in user_generator:
                    writer.write_element(user_builder.build(user))
    """

    def __init__(
        self,
        rcasp: RCASPData,
        namespace_manager: Optional[XMLNamespaceManager] = None,
    ):
        """
        Initialize BodyBuilder with RCASP data.

        Args:
            rcasp: RCASP (reporting entity) information
            namespace_manager: Namespace manager for element creation
        """
        self.rcasp = rcasp
        self.nsm = namespace_manager or get_default_namespace_manager()

    def build_doc_spec(self, doc_spec: DocSpecData) -> etree._Element:
        """
        Build DocSpec element.

        Args:
            doc_spec: Document specification data

        Returns:
            DocSpec XML element
        """
        elem = self.nsm.create_element('DocSpec')

        self.nsm.create_subelement(elem, 'DocTypeIndic', text=doc_spec.doc_type_indic)
        self.nsm.create_subelement(elem, 'DocRefId', text=doc_spec.doc_ref_id)

        if doc_spec.corr_message_ref_id:
            self.nsm.create_subelement(
                elem, 'CorrMessageRefId', text=doc_spec.corr_message_ref_id
            )

        if doc_spec.corr_doc_ref_id:
            self.nsm.create_subelement(
                elem, 'CorrDocRefId', text=doc_spec.corr_doc_ref_id
            )

        return elem

    def build_address(self, address: AddressData) -> etree._Element:
        """
        Build Address element with all sub-elements.

        Args:
            address: Address data

        Returns:
            Address XML element
        """
        elem = self.nsm.create_element('Address')

        # Add optional fields in schema order
        if address.street:
            self.nsm.create_subelement(elem, 'Street', text=address.street)

        if address.building_identifier:
            self.nsm.create_subelement(
                elem, 'BuildingIdentifier', text=address.building_identifier
            )

        if address.suite_identifier:
            self.nsm.create_subelement(
                elem, 'SuiteIdentifier', text=address.suite_identifier
            )

        if address.floor_identifier:
            self.nsm.create_subelement(
                elem, 'FloorIdentifier', text=address.floor_identifier
            )

        if address.district_name:
            self.nsm.create_subelement(
                elem, 'DistrictName', text=address.district_name
            )

        if address.pob:
            self.nsm.create_subelement(elem, 'POB', text=address.pob)

        if address.post_code:
            self.nsm.create_subelement(elem, 'PostCode', text=address.post_code)

        # Required fields
        self.nsm.create_subelement(elem, 'City', text=address.city)

        if address.country_subentity:
            self.nsm.create_subelement(
                elem, 'CountrySubentity', text=address.country_subentity
            )

        self.nsm.create_subelement(elem, 'Country', text=address.country)

        return elem

    def build_tin(self, tin: TINData) -> etree._Element:
        """
        Build TIN element with attributes.

        Args:
            tin: TIN data

        Returns:
            TIN XML element with issuedBy and optional unknown attributes
        """
        attrib = {'issuedBy': tin.issued_by}

        if tin.unknown:
            attrib['unknown'] = 'true'

        return self.nsm.create_element('TIN', text=tin.value, attrib=attrib)

    def build_rcasp(self) -> etree._Element:
        """
        Build RCASP (Reporting Crypto-Asset Service Provider) element.

        Returns:
            RCASP XML element with all sub-elements
        """
        rcasp_elem = self.nsm.create_element('RCASP')

        # DocSpec (required)
        rcasp_elem.append(self.build_doc_spec(self.rcasp.doc_spec))

        # Name (required)
        name_attrib = {}
        if self.rcasp.legal_type:
            name_attrib['legalType'] = self.rcasp.legal_type

        self.nsm.create_subelement(
            rcasp_elem, 'Name',
            text=self.rcasp.name,
            attrib=name_attrib if name_attrib else None
        )

        # TINs (optional, multiple)
        for tin in self.rcasp.tins:
            rcasp_elem.append(self.build_tin(tin))

        # Address (required)
        rcasp_elem.append(self.build_address(self.rcasp.address))

        return rcasp_elem

    def build_reporting_group(
        self,
        user_elements: Optional[List[etree._Element]] = None,
    ) -> etree._Element:
        """
        Build ReportingGroup element with RCASP and users.

        Args:
            user_elements: List of CryptoUser elements to include

        Returns:
            ReportingGroup XML element
        """
        group = self.nsm.create_element('ReportingGroup')

        # RCASP (required)
        group.append(self.build_rcasp())

        # CryptoUsers (1..n)
        if user_elements:
            for user_elem in user_elements:
                group.append(user_elem)

        return group

    def build(
        self,
        user_elements: Optional[List[etree._Element]] = None,
    ) -> etree._Element:
        """
        Build complete CARFBody element.

        Args:
            user_elements: List of CryptoUser elements to include

        Returns:
            CARFBody XML element with ReportingGroup
        """
        body = self.nsm.create_element('CARFBody')
        body.append(self.build_reporting_group(user_elements))
        return body


# =============================================================================
# Factory Functions
# =============================================================================

def create_simple_rcasp(
    name: str,
    tin: str,
    tin_country: str,
    street: str,
    city: str,
    country: str,
    post_code: Optional[str] = None,
    state: Optional[str] = None,
) -> RCASPData:
    """
    Create RCASP data with common fields.

    Args:
        name: Company name
        tin: Tax identification number
        tin_country: Country that issued TIN
        street: Street address
        city: City
        country: Country code
        post_code: Postal/ZIP code
        state: State/Province

    Returns:
        Configured RCASPData object
    """
    return RCASPData(
        name=name,
        tin=tin,
        tin_country=tin_country,
        address=AddressData(
            street=street,
            city=city,
            country=country,
            post_code=post_code,
            country_subentity=state,
        ),
    )


def create_address(
    street: str,
    city: str,
    country: str,
    post_code: Optional[str] = None,
    state: Optional[str] = None,
) -> AddressData:
    """
    Create address data with common fields.

    Args:
        street: Street address
        city: City
        country: Country code (ISO 3166-1 Alpha-2)
        post_code: Postal/ZIP code
        state: State/Province

    Returns:
        Configured AddressData object
    """
    return AddressData(
        street=street,
        city=city,
        country=country,
        post_code=post_code,
        country_subentity=state,
    )
