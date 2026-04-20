"""
CARFul XML Generation Module

Provides streaming XML generation for CARF-compliant documents.
Uses lxml.etree.xmlfile for O(1) memory footprint regardless of
transaction volume.

Components:
    - namespaces: CARF namespace management
    - stream_writer: lxml.etree.xmlfile wrapper
    - header_builder: MessageHeader generation
    - body_builder: CARFBody/ReportingGroup generation
    - user_builder: ReportableUser element generation
    - transaction_builder: Transaction element generation
"""

from .namespaces import (
    XMLNamespaceManager,
    CARF_NS,
    STF_NS,
    ISO_NS,
    XSI_NS,
    get_default_namespace_manager,
)

from .stream_writer import (
    CARFStreamWriter,
    StreamWriterConfig,
    WriteStats,
    write_carf_document,
    create_memory_writer,
    clear_element_tree,
    force_memory_cleanup,
)

from .header_builder import (
    HeaderBuilder,
    MessageHeaderData,
    Warning,
    create_new_data_header,
    create_correction_header,
    create_deletion_header,
)

from .body_builder import (
    BodyBuilder,
    RCASPData,
    AddressData,
    TINData,
    DocSpecData,
    create_simple_rcasp,
    create_address,
)

from .user_builder import (
    UserBuilder,
    IndividualData,
    EntityData,
    ControllingPersonData,
    PersonNameData,
    BirthInfoData,
    AccountHolderType,
    create_individual_user,
    create_entity_user,
)

from .transaction_builder import (
    TransactionBuilder,
    TransactionData,
    TransactionType,
    CryptoAssetData,
    FiatValueData,
    create_airdrop_transaction,
    create_staking_income_transaction,
    create_transfer_out_transaction,
    create_mining_transaction,
)

__all__ = [
    # Namespaces
    'XMLNamespaceManager',
    'CARF_NS',
    'STF_NS',
    'ISO_NS',
    'XSI_NS',
    'get_default_namespace_manager',
    # Stream Writer
    'CARFStreamWriter',
    'StreamWriterConfig',
    'WriteStats',
    'write_carf_document',
    'create_memory_writer',
    'clear_element_tree',
    'force_memory_cleanup',
    # Header Builder
    'HeaderBuilder',
    'MessageHeaderData',
    'Warning',
    'create_new_data_header',
    'create_correction_header',
    'create_deletion_header',
    # Body Builder
    'BodyBuilder',
    'RCASPData',
    'AddressData',
    'TINData',
    'DocSpecData',
    'create_simple_rcasp',
    'create_address',
    # User Builder
    'UserBuilder',
    'IndividualData',
    'EntityData',
    'ControllingPersonData',
    'PersonNameData',
    'BirthInfoData',
    'AccountHolderType',
    'create_individual_user',
    'create_entity_user',
    # Transaction Builder
    'TransactionBuilder',
    'TransactionData',
    'TransactionType',
    'CryptoAssetData',
    'FiatValueData',
    'create_airdrop_transaction',
    'create_staking_income_transaction',
    'create_transfer_out_transaction',
    'create_mining_transaction',
]
