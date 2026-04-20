"""
CARFul - CryptoUser (Reportable User) Builder

Builds CryptoUser XML elements for individuals and entities with
their associated transactions.

CryptoUser Structure (per OECD CARF XSD v1.5):
    - CryptoUser
      - DocSpec
      - AccountHolderType (CARF101=Individual, CARF102=Entity, CARF103=Entity+CP)
      - Individual | Entity
        - Name
        - TIN (optional, multiple)
        - Address (optional)
        - Nationality (optional, for individuals)
        - BirthInfo (optional, for individuals)
        - ControllingPerson (optional, for entities)
      - Transaction (1..n)

Usage:
    from xml_gen.user_builder import UserBuilder, IndividualData, EntityData

    # Individual user
    individual = IndividualData(
        first_name='John',
        last_name='Doe',
        tin='123-45-6789',
        tin_country='US',
        birth_date=date(1980, 1, 15),
    )
    builder = UserBuilder(individual=individual)
    user_element = builder.build(transaction_elements)

    # Entity user
    entity = EntityData(
        name='Acme Corp',
        tin='12-3456789',
        tin_country='US',
    )
    builder = UserBuilder(entity=entity)
"""

import uuid
from datetime import date
from typing import List, Optional, Union
from dataclasses import dataclass, field
from lxml import etree

from .namespaces import (
    XMLNamespaceManager,
    get_default_namespace_manager,
)
from .body_builder import (
    AddressData,
    TINData,
    DocSpecData,
)


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class PersonNameData:
    """Name data for an individual."""
    last_name: str
    first_name: Optional[str] = None
    middle_name: Optional[str] = None
    name_prefix: Optional[str] = None  # Mr., Mrs., Dr.
    name_suffix: Optional[str] = None  # Jr., III

    def __post_init__(self):
        if not self.last_name:
            raise ValueError("last_name is required")


@dataclass
class BirthInfoData:
    """Birth information for an individual."""
    birth_date: date
    city: Optional[str] = None
    country: Optional[str] = None  # ISO 3166-1 Alpha-2

    def __post_init__(self):
        if self.country:
            self.country = self.country.upper()


@dataclass
class IndividualData:
    """
    Individual (natural person) reportable user data.

    Represents a person who uses crypto-asset services.
    """
    # Name (required)
    last_name: str
    first_name: Optional[str] = None
    middle_name: Optional[str] = None
    name_prefix: Optional[str] = None
    name_suffix: Optional[str] = None

    # TINs (optional)
    tins: List[TINData] = field(default_factory=list)

    # Convenience for single TIN
    tin: Optional[str] = None
    tin_country: Optional[str] = None

    # Address (optional)
    address: Optional[AddressData] = None

    # Nationality (optional, multiple)
    nationalities: List[str] = field(default_factory=list)

    # Birth info (optional)
    birth_date: Optional[date] = None
    birth_city: Optional[str] = None
    birth_country: Optional[str] = None

    # Document spec
    doc_spec: Optional[DocSpecData] = None

    def __post_init__(self):
        if not self.last_name:
            raise ValueError("last_name is required for Individual")

        if self.doc_spec is None:
            self.doc_spec = DocSpecData()

        # Add single TIN to list
        if self.tin and self.tin_country:
            self.tins.append(TINData(value=self.tin, issued_by=self.tin_country))

        # Normalize nationality codes
        self.nationalities = [n.upper() for n in self.nationalities]

    @property
    def name(self) -> PersonNameData:
        """Get PersonNameData from individual fields."""
        return PersonNameData(
            first_name=self.first_name,
            middle_name=self.middle_name,
            last_name=self.last_name,
            name_prefix=self.name_prefix,
            name_suffix=self.name_suffix,
        )

    @property
    def birth_info(self) -> Optional[BirthInfoData]:
        """Get BirthInfoData if birth_date is set."""
        if self.birth_date:
            return BirthInfoData(
                birth_date=self.birth_date,
                city=self.birth_city,
                country=self.birth_country,
            )
        return None


@dataclass
class ControllingPersonData:
    """
    Controlling person of an entity.

    Natural persons who exercise control over entities.
    """
    last_name: str
    first_name: Optional[str] = None
    tins: List[TINData] = field(default_factory=list)
    address: Optional[AddressData] = None
    nationalities: List[str] = field(default_factory=list)
    birth_date: Optional[date] = None
    birth_city: Optional[str] = None
    birth_country: Optional[str] = None

    # Convenience for single TIN
    tin: Optional[str] = None
    tin_country: Optional[str] = None

    def __post_init__(self):
        if self.tin and self.tin_country:
            self.tins.append(TINData(value=self.tin, issued_by=self.tin_country))
        self.nationalities = [n.upper() for n in self.nationalities]


@dataclass
class EntityData:
    """
    Entity (organization) reportable user data.

    Represents a company/organization that uses crypto-asset services.
    """
    name: str
    legal_type: Optional[str] = None  # LLC, Corp, Ltd

    # TINs (optional)
    tins: List[TINData] = field(default_factory=list)

    # Convenience for single TIN
    tin: Optional[str] = None
    tin_country: Optional[str] = None

    # Address (optional)
    address: Optional[AddressData] = None

    # Controlling persons (optional)
    controlling_persons: List[ControllingPersonData] = field(default_factory=list)

    # Document spec
    doc_spec: Optional[DocSpecData] = None

    def __post_init__(self):
        if not self.name:
            raise ValueError("name is required for Entity")

        if self.doc_spec is None:
            self.doc_spec = DocSpecData()

        # Add single TIN to list
        if self.tin and self.tin_country:
            self.tins.append(TINData(value=self.tin, issued_by=self.tin_country))

    @property
    def has_controlling_persons(self) -> bool:
        """Check if entity has controlling persons."""
        return len(self.controlling_persons) > 0


# =============================================================================
# Account Holder Types
# =============================================================================

class AccountHolderType:
    """CARF Account Holder Type codes."""
    INDIVIDUAL = 'CARF101'
    ENTITY = 'CARF102'
    ENTITY_WITH_CONTROLLING_PERSONS = 'CARF103'


# =============================================================================
# User Builder
# =============================================================================

class UserBuilder:
    """
    Builder for CryptoUser XML elements.

    Creates properly structured CryptoUser elements for either
    individuals or entities with their transactions.

    Example:
        # Individual
        builder = UserBuilder(individual=individual_data)
        user = builder.build(transaction_elements)

        # Entity
        builder = UserBuilder(entity=entity_data)
        user = builder.build(transaction_elements)
    """

    def __init__(
        self,
        individual: Optional[IndividualData] = None,
        entity: Optional[EntityData] = None,
        namespace_manager: Optional[XMLNamespaceManager] = None,
    ):
        """
        Initialize UserBuilder with user data.

        Args:
            individual: Individual user data (mutually exclusive with entity)
            entity: Entity user data (mutually exclusive with individual)
            namespace_manager: Namespace manager for element creation

        Raises:
            ValueError: If both or neither individual/entity provided
        """
        if individual and entity:
            raise ValueError("Cannot specify both individual and entity")
        if not individual and not entity:
            raise ValueError("Must specify either individual or entity")

        self.individual = individual
        self.entity = entity
        self.nsm = namespace_manager or get_default_namespace_manager()

    @property
    def is_individual(self) -> bool:
        """Check if this is an individual user."""
        return self.individual is not None

    @property
    def account_holder_type(self) -> str:
        """Get the appropriate account holder type code."""
        if self.is_individual:
            return AccountHolderType.INDIVIDUAL
        elif self.entity.has_controlling_persons:
            return AccountHolderType.ENTITY_WITH_CONTROLLING_PERSONS
        else:
            return AccountHolderType.ENTITY

    @property
    def doc_spec(self) -> DocSpecData:
        """Get document specification."""
        if self.is_individual:
            return self.individual.doc_spec
        return self.entity.doc_spec

    def _build_person_name(self, name: PersonNameData) -> etree._Element:
        """Build person Name element."""
        elem = self.nsm.create_element('Name')

        if name.first_name:
            self.nsm.create_subelement(elem, 'FirstName', text=name.first_name)

        if name.middle_name:
            self.nsm.create_subelement(elem, 'MiddleName', text=name.middle_name)

        self.nsm.create_subelement(elem, 'LastName', text=name.last_name)

        if name.name_prefix:
            self.nsm.create_subelement(elem, 'NamePrefix', text=name.name_prefix)

        if name.name_suffix:
            self.nsm.create_subelement(elem, 'NameSuffix', text=name.name_suffix)

        return elem

    def _build_org_name(self, name: str, legal_type: Optional[str]) -> etree._Element:
        """Build organization Name element."""
        attrib = {}
        if legal_type:
            attrib['legalType'] = legal_type

        return self.nsm.create_element(
            'Name',
            text=name,
            attrib=attrib if attrib else None
        )

    def _build_tin(self, tin: TINData) -> etree._Element:
        """Build TIN element with attributes."""
        attrib = {'issuedBy': tin.issued_by}
        if tin.unknown:
            attrib['unknown'] = 'true'
        return self.nsm.create_element('TIN', text=tin.value, attrib=attrib)

    def _build_address(self, address: AddressData) -> etree._Element:
        """Build Address element."""
        elem = self.nsm.create_element('Address')

        if address.street:
            self.nsm.create_subelement(elem, 'Street', text=address.street)
        if address.building_identifier:
            self.nsm.create_subelement(elem, 'BuildingIdentifier', text=address.building_identifier)
        if address.suite_identifier:
            self.nsm.create_subelement(elem, 'SuiteIdentifier', text=address.suite_identifier)
        if address.floor_identifier:
            self.nsm.create_subelement(elem, 'FloorIdentifier', text=address.floor_identifier)
        if address.district_name:
            self.nsm.create_subelement(elem, 'DistrictName', text=address.district_name)
        if address.pob:
            self.nsm.create_subelement(elem, 'POB', text=address.pob)
        if address.post_code:
            self.nsm.create_subelement(elem, 'PostCode', text=address.post_code)

        self.nsm.create_subelement(elem, 'City', text=address.city)

        if address.country_subentity:
            self.nsm.create_subelement(elem, 'CountrySubentity', text=address.country_subentity)

        self.nsm.create_subelement(elem, 'Country', text=address.country)

        return elem

    def _build_birth_info(self, birth_info: BirthInfoData) -> etree._Element:
        """Build BirthInfo element."""
        elem = self.nsm.create_element('BirthInfo')

        self.nsm.create_subelement(
            elem, 'BirthDate',
            text=birth_info.birth_date.isoformat()
        )

        if birth_info.city:
            self.nsm.create_subelement(elem, 'City', text=birth_info.city)

        if birth_info.country:
            self.nsm.create_subelement(elem, 'Country', text=birth_info.country)

        return elem

    def _build_doc_spec(self, doc_spec: DocSpecData) -> etree._Element:
        """Build DocSpec element."""
        elem = self.nsm.create_element('DocSpec')

        self.nsm.create_subelement(elem, 'DocTypeIndic', text=doc_spec.doc_type_indic)
        self.nsm.create_subelement(elem, 'DocRefId', text=doc_spec.doc_ref_id)

        if doc_spec.corr_message_ref_id:
            self.nsm.create_subelement(elem, 'CorrMessageRefId', text=doc_spec.corr_message_ref_id)

        if doc_spec.corr_doc_ref_id:
            self.nsm.create_subelement(elem, 'CorrDocRefId', text=doc_spec.corr_doc_ref_id)

        return elem

    def _build_individual(self) -> etree._Element:
        """Build Individual element."""
        ind = self.individual
        elem = self.nsm.create_element('Individual')

        # Name (required)
        elem.append(self._build_person_name(ind.name))

        # TINs (optional)
        for tin in ind.tins:
            elem.append(self._build_tin(tin))

        # Address (optional)
        if ind.address:
            elem.append(self._build_address(ind.address))

        # Nationalities (optional)
        for nationality in ind.nationalities:
            self.nsm.create_subelement(elem, 'Nationality', text=nationality)

        # BirthInfo (optional)
        if ind.birth_info:
            elem.append(self._build_birth_info(ind.birth_info))

        return elem

    def _build_controlling_person(self, cp: ControllingPersonData) -> etree._Element:
        """Build ControllingPerson element."""
        elem = self.nsm.create_element('ControllingPerson')

        # Name
        name = PersonNameData(
            first_name=cp.first_name,
            last_name=cp.last_name,
        )
        elem.append(self._build_person_name(name))

        # TINs
        for tin in cp.tins:
            elem.append(self._build_tin(tin))

        # Address
        if cp.address:
            elem.append(self._build_address(cp.address))

        # Nationalities
        for nationality in cp.nationalities:
            self.nsm.create_subelement(elem, 'Nationality', text=nationality)

        # BirthInfo
        if cp.birth_date:
            birth_info = BirthInfoData(
                birth_date=cp.birth_date,
                city=cp.birth_city,
                country=cp.birth_country,
            )
            elem.append(self._build_birth_info(birth_info))

        return elem

    def _build_entity(self) -> etree._Element:
        """Build Entity element."""
        ent = self.entity
        elem = self.nsm.create_element('Entity')

        # Name (required)
        elem.append(self._build_org_name(ent.name, ent.legal_type))

        # TINs (optional)
        for tin in ent.tins:
            elem.append(self._build_tin(tin))

        # Address (optional)
        if ent.address:
            elem.append(self._build_address(ent.address))

        # Controlling Persons (optional)
        for cp in ent.controlling_persons:
            elem.append(self._build_controlling_person(cp))

        return elem

    def build(
        self,
        transaction_elements: Optional[List[etree._Element]] = None,
    ) -> etree._Element:
        """
        Build complete CryptoUser element.

        Args:
            transaction_elements: List of Transaction elements to include

        Returns:
            CryptoUser XML element
        """
        user = self.nsm.create_element('CryptoUser')

        # DocSpec (required)
        user.append(self._build_doc_spec(self.doc_spec))

        # AccountHolderType (required)
        self.nsm.create_subelement(
            user, 'AccountHolderType',
            text=self.account_holder_type
        )

        # Individual or Entity (required, choice)
        if self.is_individual:
            user.append(self._build_individual())
        else:
            user.append(self._build_entity())

        # Transactions (1..n)
        if transaction_elements:
            for txn in transaction_elements:
                user.append(txn)

        return user


# =============================================================================
# Factory Functions
# =============================================================================

def create_individual_user(
    first_name: str,
    last_name: str,
    tin: Optional[str] = None,
    tin_country: Optional[str] = None,
    birth_date: Optional[date] = None,
) -> IndividualData:
    """Create a simple individual user."""
    return IndividualData(
        first_name=first_name,
        last_name=last_name,
        tin=tin,
        tin_country=tin_country,
        birth_date=birth_date,
    )


def create_entity_user(
    name: str,
    tin: Optional[str] = None,
    tin_country: Optional[str] = None,
    legal_type: Optional[str] = None,
) -> EntityData:
    """Create a simple entity user."""
    return EntityData(
        name=name,
        tin=tin,
        tin_country=tin_country,
        legal_type=legal_type,
    )
