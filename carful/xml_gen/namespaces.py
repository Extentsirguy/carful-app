"""
CARFul - XML Namespace Management

Manages CARF XML namespaces and provides utilities for namespace-aware
element creation. Follows OECD CARF XML Schema v1.5 namespace requirements.

Namespaces:
    - CARF (urn:oecd:ties:carf:v1): Main CARF elements
    - STF (urn:oecd:ties:stf:v1): Standard OECD types
    - ISO (urn:oecd:ties:isocarf:v1): ISO code types
    - XSI (http://www.w3.org/2001/XMLSchema-instance): Schema instance

Usage:
    from xml_gen.namespaces import XMLNamespaceManager, CARF_NS

    nsm = XMLNamespaceManager()
    element = nsm.create_element('CARF')
    element.set(nsm.qname('version'), '1.5')
"""

from typing import Dict, Optional, Tuple
from lxml import etree
from dataclasses import dataclass


# =============================================================================
# Namespace Constants
# =============================================================================

# Primary CARF namespace - main elements
CARF_NS = "urn:oecd:ties:carf:v1"

# Standard OECD types namespace
STF_NS = "urn:oecd:ties:stf:v1"

# ISO code types namespace (countries, currencies)
ISO_NS = "urn:oecd:ties:isocarf:v1"

# XML Schema Instance namespace (for xsi:schemaLocation)
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"

# Default namespace prefix mapping
DEFAULT_NSMAP = {
    None: CARF_NS,      # Default namespace (no prefix)
    'carf': CARF_NS,    # Explicit CARF prefix
    'stf': STF_NS,      # Standard types
    'iso': ISO_NS,      # ISO codes
    'xsi': XSI_NS,      # Schema instance
}


# =============================================================================
# Namespace Manager
# =============================================================================

@dataclass
class NamespaceConfig:
    """Configuration for namespace handling."""
    include_schema_location: bool = True
    schema_location: str = "urn:oecd:ties:carf:v1 CARFXML_v1.xsd"
    default_namespace: str = CARF_NS


class XMLNamespaceManager:
    """
    Manages XML namespaces for CARF document generation.

    Provides utilities for:
    - Creating namespace-aware elements
    - Building qualified names (QNames)
    - Generating namespace maps for lxml
    - Handling schema location attributes

    Example:
        nsm = XMLNamespaceManager()

        # Create root element with all namespaces
        root = nsm.create_root_element('CARF', version='1.5')

        # Create child element in default namespace
        header = nsm.create_element('MessageHeader')
        root.append(header)

        # Create element with explicit namespace
        country = nsm.create_element('Country', namespace=ISO_NS)
    """

    def __init__(
        self,
        config: Optional[NamespaceConfig] = None,
        custom_nsmap: Optional[Dict[Optional[str], str]] = None
    ):
        """
        Initialize namespace manager.

        Args:
            config: Namespace configuration options
            custom_nsmap: Custom namespace prefix mapping (merged with defaults)
        """
        self.config = config or NamespaceConfig()
        self._nsmap = DEFAULT_NSMAP.copy()

        if custom_nsmap:
            self._nsmap.update(custom_nsmap)

        # Build reverse mapping for namespace lookup
        self._ns_to_prefix: Dict[str, Optional[str]] = {
            v: k for k, v in self._nsmap.items()
        }

    @property
    def nsmap(self) -> Dict[Optional[str], str]:
        """Get the complete namespace map for lxml."""
        return self._nsmap.copy()

    @property
    def default_namespace(self) -> str:
        """Get the default (unprefixed) namespace."""
        return self._nsmap.get(None, CARF_NS)

    def qname(self, local_name: str, namespace: Optional[str] = None) -> str:
        """
        Create a qualified name (Clark notation) for lxml.

        Args:
            local_name: Local element/attribute name
            namespace: Namespace URI (uses default if None)

        Returns:
            Clark notation string: {namespace}local_name

        Example:
            nsm.qname('CARF')  # '{urn:oecd:ties:carf:v1}CARF'
            nsm.qname('Country', ISO_NS)  # '{urn:oecd:ties:isocarf:v1}Country'
        """
        ns = namespace or self.default_namespace
        return f"{{{ns}}}{local_name}"

    def get_prefix(self, namespace: str) -> Optional[str]:
        """
        Get the prefix for a namespace URI.

        Args:
            namespace: Namespace URI

        Returns:
            Prefix string or None for default namespace
        """
        return self._ns_to_prefix.get(namespace)

    def create_element(
        self,
        local_name: str,
        namespace: Optional[str] = None,
        text: Optional[str] = None,
        attrib: Optional[Dict[str, str]] = None,
        nsmap: Optional[Dict[Optional[str], str]] = None,
    ) -> etree._Element:
        """
        Create an XML element with namespace awareness.

        Args:
            local_name: Element name (without namespace prefix)
            namespace: Namespace URI (uses default if None)
            text: Text content for the element
            attrib: Dictionary of attributes
            nsmap: Namespace map for this element (uses manager's if None)

        Returns:
            lxml Element object

        Example:
            header = nsm.create_element('MessageHeader')
            header = nsm.create_element('TransmittingCountry', text='US')
        """
        qn = self.qname(local_name, namespace)
        element_nsmap = nsmap if nsmap is not None else None  # Don't add nsmap to children

        element = etree.Element(qn, attrib=attrib, nsmap=element_nsmap)

        if text is not None:
            element.text = str(text)

        return element

    def create_subelement(
        self,
        parent: etree._Element,
        local_name: str,
        namespace: Optional[str] = None,
        text: Optional[str] = None,
        attrib: Optional[Dict[str, str]] = None,
    ) -> etree._Element:
        """
        Create a child element and append to parent.

        Args:
            parent: Parent element
            local_name: Child element name
            namespace: Namespace URI (uses default if None)
            text: Text content
            attrib: Dictionary of attributes

        Returns:
            Newly created child element
        """
        qn = self.qname(local_name, namespace)
        element = etree.SubElement(parent, qn, attrib=attrib)

        if text is not None:
            element.text = str(text)

        return element

    def create_root_element(
        self,
        local_name: str = 'CARF',
        version: str = '1.5',
        include_schema_location: Optional[bool] = None,
    ) -> etree._Element:
        """
        Create the root CARF element with all namespace declarations.

        Args:
            local_name: Root element name (default: 'CARF')
            version: CARF schema version (default: '1.5')
            include_schema_location: Whether to add xsi:schemaLocation

        Returns:
            Root element with namespace declarations

        Example:
            root = nsm.create_root_element()
            # Creates: <CARF xmlns="urn:oecd:ties:carf:v1" version="1.5">
        """
        root = etree.Element(
            self.qname(local_name),
            nsmap=self._nsmap
        )

        # Set version attribute
        root.set('version', version)

        # Add schema location if configured
        should_add_schema = (
            include_schema_location
            if include_schema_location is not None
            else self.config.include_schema_location
        )

        if should_add_schema:
            root.set(
                self.qname('schemaLocation', XSI_NS),
                self.config.schema_location
            )

        return root

    def get_namespace_declarations(self) -> str:
        """
        Get namespace declarations as XML attribute string.

        Returns:
            String of xmlns declarations for manual XML building

        Example:
            'xmlns="urn:oecd:ties:carf:v1" xmlns:stf="urn:oecd:ties:stf:v1"'
        """
        declarations = []

        for prefix, uri in self._nsmap.items():
            if prefix is None:
                declarations.append(f'xmlns="{uri}"')
            else:
                declarations.append(f'xmlns:{prefix}="{uri}"')

        return ' '.join(declarations)


# =============================================================================
# Utility Functions
# =============================================================================

def create_qname(local_name: str, namespace: str = CARF_NS) -> str:
    """
    Convenience function to create a qualified name.

    Args:
        local_name: Element/attribute name
        namespace: Namespace URI

    Returns:
        Clark notation QName string
    """
    return f"{{{namespace}}}{local_name}"


def parse_qname(qname: str) -> Tuple[str, str]:
    """
    Parse a Clark notation QName into namespace and local name.

    Args:
        qname: Clark notation string like '{namespace}local_name'

    Returns:
        Tuple of (namespace, local_name)

    Raises:
        ValueError: If qname is not in Clark notation
    """
    if not qname.startswith('{'):
        raise ValueError(f"Not a Clark notation QName: {qname}")

    ns_end = qname.find('}')
    if ns_end == -1:
        raise ValueError(f"Invalid Clark notation QName: {qname}")

    namespace = qname[1:ns_end]
    local_name = qname[ns_end + 1:]

    return namespace, local_name


def get_default_namespace_manager() -> XMLNamespaceManager:
    """
    Get a default namespace manager instance.

    Returns:
        XMLNamespaceManager with default configuration
    """
    return XMLNamespaceManager()


# =============================================================================
# Namespace Registry (for extension support)
# =============================================================================

class NamespaceRegistry:
    """
    Registry for managing multiple namespace configurations.

    Useful for supporting multiple CARF schema versions or
    extensions in the future.
    """

    _registrations: Dict[str, XMLNamespaceManager] = {}

    @classmethod
    def register(cls, name: str, manager: XMLNamespaceManager) -> None:
        """Register a namespace manager with a name."""
        cls._registrations[name] = manager

    @classmethod
    def get(cls, name: str) -> Optional[XMLNamespaceManager]:
        """Get a registered namespace manager by name."""
        return cls._registrations.get(name)

    @classmethod
    def get_or_default(cls, name: str) -> XMLNamespaceManager:
        """Get a registered manager or return default."""
        return cls._registrations.get(name) or get_default_namespace_manager()


# Register default CARF v1.5 manager
NamespaceRegistry.register('carf_v1.5', XMLNamespaceManager())
