"""
CARFul - Transaction Builder

Builds Transaction XML elements for crypto-asset transactions.
Supports all CARF transaction types (exchanges, transfers, payments).

Transaction Structure (per OECD CARF XSD v1.5):
    - Transaction
      - DocSpec
      - TransactionType (CARF401-CARF606)
      - TransactionId (optional)
      - TransactionDate
      - CryptoAsset
        - AssetCode
        - Amount (20 decimal precision)
        - AssetName (optional)
      - FiatValue (optional)
      - Fee (optional)
      - FeeFiat (optional)
      - DestinationAddress (optional, for transfers out)
      - SourceAddress (optional, for transfers in)
      - Notes (optional)

CARF Transaction Type Codes:
    CARF4xx - Exchange Transactions:
        CARF401: Staking
        CARF402: Crypto Loan
        CARF403: Wrapping
        CARF404: Collateral

    CARF5xx - Transfer In:
        CARF501: Airdrop
        CARF502: Staking Income
        CARF503: Mining
        CARF504: Hard Fork
        CARF505: Transfer from RCASP
        CARF506: Retail Payment Received
        CARF507: Other Transfer In
        CARF508: Initial Acquisition
        CARF509: Crypto Loan Received

    CARF6xx - Transfer Out:
        CARF601: Transfer to RCASP
        CARF602: Transfer to Non-RCASP
        CARF603: Retail Payment Made
        CARF604: Gift/Donation Out
        CARF605: Lost/Stolen
        CARF606: Other Transfer Out

Usage:
    from xml_gen.transaction_builder import TransactionBuilder, TransactionData

    txn = TransactionData(
        transaction_type='CARF501',
        transaction_date=datetime(2025, 3, 15, 10, 30, 0),
        asset_code='BTC',
        amount=Decimal('0.05'),
        fiat_value=Decimal('2500.00'),
        fiat_currency='USD',
    )
    builder = TransactionBuilder(txn)
    element = builder.build()
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional
from dataclasses import dataclass
from lxml import etree

from .namespaces import (
    XMLNamespaceManager,
    get_default_namespace_manager,
)
from .body_builder import DocSpecData


# =============================================================================
# Transaction Type Constants
# =============================================================================

class TransactionType:
    """CARF Transaction Type codes."""

    # Exchange Transactions (CARF4xx)
    STAKING = 'CARF401'
    CRYPTO_LOAN = 'CARF402'
    WRAPPING = 'CARF403'
    COLLATERAL = 'CARF404'

    # Transfer In (CARF5xx)
    AIRDROP = 'CARF501'
    STAKING_INCOME = 'CARF502'
    MINING = 'CARF503'
    HARD_FORK = 'CARF504'
    TRANSFER_FROM_RCASP = 'CARF505'
    RETAIL_PAYMENT_RECEIVED = 'CARF506'
    OTHER_TRANSFER_IN = 'CARF507'
    INITIAL_ACQUISITION = 'CARF508'
    CRYPTO_LOAN_RECEIVED = 'CARF509'

    # Transfer Out (CARF6xx)
    TRANSFER_TO_RCASP = 'CARF601'
    TRANSFER_TO_NON_RCASP = 'CARF602'
    RETAIL_PAYMENT_MADE = 'CARF603'
    GIFT_DONATION_OUT = 'CARF604'
    LOST_STOLEN = 'CARF605'
    OTHER_TRANSFER_OUT = 'CARF606'

    # All valid codes
    ALL_CODES = {
        STAKING, CRYPTO_LOAN, WRAPPING, COLLATERAL,
        AIRDROP, STAKING_INCOME, MINING, HARD_FORK, TRANSFER_FROM_RCASP,
        RETAIL_PAYMENT_RECEIVED, OTHER_TRANSFER_IN, INITIAL_ACQUISITION,
        CRYPTO_LOAN_RECEIVED,
        TRANSFER_TO_RCASP, TRANSFER_TO_NON_RCASP, RETAIL_PAYMENT_MADE,
        GIFT_DONATION_OUT, LOST_STOLEN, OTHER_TRANSFER_OUT,
    }

    @classmethod
    def is_valid(cls, code: str) -> bool:
        """Check if a transaction type code is valid."""
        return code in cls.ALL_CODES

    @classmethod
    def is_transfer_in(cls, code: str) -> bool:
        """Check if transaction type is a transfer in."""
        return code.startswith('CARF5')

    @classmethod
    def is_transfer_out(cls, code: str) -> bool:
        """Check if transaction type is a transfer out."""
        return code.startswith('CARF6')

    @classmethod
    def is_exchange(cls, code: str) -> bool:
        """Check if transaction type is an exchange."""
        return code.startswith('CARF4')


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class CryptoAssetData:
    """
    Crypto asset details for a transaction.

    Supports 20 decimal precision per OECD XSD requirements.
    """
    asset_code: str  # e.g., BTC, ETH, USDT
    amount: Decimal  # 20 decimal precision
    asset_name: Optional[str] = None  # e.g., "Bitcoin"

    def __post_init__(self):
        if not self.asset_code:
            raise ValueError("asset_code is required")

        # Ensure amount is Decimal
        if not isinstance(self.amount, Decimal):
            self.amount = Decimal(str(self.amount))

        # Validate precision (max 20 decimals, 40 total digits)
        if self.amount.as_tuple().exponent < -20:
            raise ValueError("Amount exceeds maximum 20 decimal places")

    def format_amount(self) -> str:
        """Format amount with proper precision."""
        # Remove trailing zeros but keep reasonable precision
        normalized = self.amount.normalize()
        return str(normalized)


@dataclass
class FiatValueData:
    """Fiat currency value for a transaction."""
    amount: Decimal
    currency: str  # ISO 4217 code (USD, EUR, GBP)

    def __post_init__(self):
        if not self.currency or len(self.currency) != 3:
            raise ValueError("currency must be a 3-letter ISO 4217 code")
        self.currency = self.currency.upper()

        if not isinstance(self.amount, Decimal):
            self.amount = Decimal(str(self.amount))

    def format_amount(self) -> str:
        """Format amount for XML."""
        return str(self.amount.quantize(Decimal('0.0001')))


@dataclass
class TransactionData:
    """
    Complete transaction data for CARF reporting.

    Contains all fields needed to build a Transaction XML element.
    """
    # Required fields
    transaction_type: str  # CARF401-CARF606
    transaction_date: datetime
    asset_code: str
    amount: Decimal

    # Optional identification
    transaction_id: Optional[str] = None  # Blockchain hash, exchange ID

    # Optional asset name
    asset_name: Optional[str] = None

    # Optional fiat value
    fiat_value: Optional[Decimal] = None
    fiat_currency: Optional[str] = None

    # Optional fees
    fee_amount: Optional[Decimal] = None
    fee_currency: Optional[str] = None  # Same as asset_code if crypto fee
    fee_fiat_amount: Optional[Decimal] = None
    fee_fiat_currency: Optional[str] = None

    # Optional addresses
    destination_address: Optional[str] = None  # For transfers out
    source_address: Optional[str] = None  # For transfers in

    # Optional notes
    notes: Optional[str] = None

    # Document spec
    doc_spec: Optional[DocSpecData] = None

    def __post_init__(self):
        # Validate transaction type
        if not TransactionType.is_valid(self.transaction_type):
            raise ValueError(
                f"Invalid transaction_type: {self.transaction_type}. "
                f"Must be one of CARF401-CARF606"
            )

        # Auto-generate doc spec
        if self.doc_spec is None:
            self.doc_spec = DocSpecData()

        # Ensure Decimal types
        if not isinstance(self.amount, Decimal):
            self.amount = Decimal(str(self.amount))

        if self.fiat_value is not None and not isinstance(self.fiat_value, Decimal):
            self.fiat_value = Decimal(str(self.fiat_value))

        if self.fee_amount is not None and not isinstance(self.fee_amount, Decimal):
            self.fee_amount = Decimal(str(self.fee_amount))

        if self.fee_fiat_amount is not None and not isinstance(self.fee_fiat_amount, Decimal):
            self.fee_fiat_amount = Decimal(str(self.fee_fiat_amount))

    @property
    def crypto_asset(self) -> CryptoAssetData:
        """Get CryptoAssetData from transaction fields."""
        return CryptoAssetData(
            asset_code=self.asset_code,
            amount=self.amount,
            asset_name=self.asset_name,
        )

    @property
    def has_fiat_value(self) -> bool:
        """Check if fiat value is set."""
        return self.fiat_value is not None and self.fiat_currency is not None

    @property
    def has_fee(self) -> bool:
        """Check if crypto fee is set."""
        return self.fee_amount is not None

    @property
    def has_fiat_fee(self) -> bool:
        """Check if fiat fee is set."""
        return self.fee_fiat_amount is not None and self.fee_fiat_currency is not None


# =============================================================================
# Transaction Builder
# =============================================================================

class TransactionBuilder:
    """
    Builder for Transaction XML elements.

    Creates properly structured Transaction elements following
    the OECD CARF XSD v1.5 specification.

    Example:
        txn = TransactionData(
            transaction_type='CARF501',
            transaction_date=datetime.now(),
            asset_code='BTC',
            amount=Decimal('0.05'),
        )
        builder = TransactionBuilder(txn)
        element = builder.build()
    """

    def __init__(
        self,
        data: TransactionData,
        namespace_manager: Optional[XMLNamespaceManager] = None,
    ):
        """
        Initialize TransactionBuilder.

        Args:
            data: Transaction data
            namespace_manager: Namespace manager for element creation
        """
        self.data = data
        self.nsm = namespace_manager or get_default_namespace_manager()

    def _build_doc_spec(self) -> etree._Element:
        """Build DocSpec element."""
        doc_spec = self.data.doc_spec
        elem = self.nsm.create_element('DocSpec')

        self.nsm.create_subelement(elem, 'DocTypeIndic', text=doc_spec.doc_type_indic)
        self.nsm.create_subelement(elem, 'DocRefId', text=doc_spec.doc_ref_id)

        if doc_spec.corr_message_ref_id:
            self.nsm.create_subelement(elem, 'CorrMessageRefId', text=doc_spec.corr_message_ref_id)

        if doc_spec.corr_doc_ref_id:
            self.nsm.create_subelement(elem, 'CorrDocRefId', text=doc_spec.corr_doc_ref_id)

        return elem

    def _build_crypto_asset(self) -> etree._Element:
        """Build CryptoAsset element."""
        asset = self.data.crypto_asset
        elem = self.nsm.create_element('CryptoAsset')

        self.nsm.create_subelement(elem, 'AssetCode', text=asset.asset_code)
        self.nsm.create_subelement(elem, 'Amount', text=asset.format_amount())

        if asset.asset_name:
            self.nsm.create_subelement(elem, 'AssetName', text=asset.asset_name)

        return elem

    def _build_fiat_value(self) -> Optional[etree._Element]:
        """Build FiatValue element if present."""
        if not self.data.has_fiat_value:
            return None

        fiat = FiatValueData(
            amount=self.data.fiat_value,
            currency=self.data.fiat_currency,
        )

        return self.nsm.create_element(
            'FiatValue',
            text=fiat.format_amount(),
            attrib={'currCode': fiat.currency}
        )

    def _build_fee(self) -> Optional[etree._Element]:
        """Build Fee element if present."""
        if not self.data.has_fee:
            return None

        fee_currency = self.data.fee_currency or self.data.asset_code

        return self.nsm.create_element(
            'Fee',
            text=str(self.data.fee_amount.normalize()),
            attrib={'assetCode': fee_currency}
        )

    def _build_fee_fiat(self) -> Optional[etree._Element]:
        """Build FeeFiat element if present."""
        if not self.data.has_fiat_fee:
            return None

        return self.nsm.create_element(
            'FeeFiat',
            text=str(self.data.fee_fiat_amount.quantize(Decimal('0.0001'))),
            attrib={'currCode': self.data.fee_fiat_currency}
        )

    def _format_datetime(self, dt: datetime) -> str:
        """Format datetime as ISO 8601 with UTC timezone."""
        return dt.strftime('%Y-%m-%dT%H:%M:%SZ')

    def build(self) -> etree._Element:
        """
        Build complete Transaction XML element.

        Returns:
            Transaction XML element with all sub-elements
        """
        txn = self.nsm.create_element('Transaction')

        # DocSpec (required)
        txn.append(self._build_doc_spec())

        # TransactionType (required)
        self.nsm.create_subelement(
            txn, 'TransactionType',
            text=self.data.transaction_type
        )

        # TransactionId (optional)
        if self.data.transaction_id:
            self.nsm.create_subelement(
                txn, 'TransactionId',
                text=self.data.transaction_id
            )

        # TransactionDate (required)
        self.nsm.create_subelement(
            txn, 'TransactionDate',
            text=self._format_datetime(self.data.transaction_date)
        )

        # CryptoAsset (required)
        txn.append(self._build_crypto_asset())

        # FiatValue (optional)
        fiat_elem = self._build_fiat_value()
        if fiat_elem is not None:
            txn.append(fiat_elem)

        # Fee (optional)
        fee_elem = self._build_fee()
        if fee_elem is not None:
            txn.append(fee_elem)

        # FeeFiat (optional)
        fee_fiat_elem = self._build_fee_fiat()
        if fee_fiat_elem is not None:
            txn.append(fee_fiat_elem)

        # DestinationAddress (optional)
        if self.data.destination_address:
            self.nsm.create_subelement(
                txn, 'DestinationAddress',
                text=self.data.destination_address
            )

        # SourceAddress (optional)
        if self.data.source_address:
            self.nsm.create_subelement(
                txn, 'SourceAddress',
                text=self.data.source_address
            )

        # Notes (optional)
        if self.data.notes:
            self.nsm.create_subelement(txn, 'Notes', text=self.data.notes)

        return txn


# =============================================================================
# Factory Functions
# =============================================================================

def create_airdrop_transaction(
    transaction_date: datetime,
    asset_code: str,
    amount: Decimal,
    fiat_value: Optional[Decimal] = None,
    fiat_currency: str = 'USD',
) -> TransactionData:
    """Create an airdrop (CARF501) transaction."""
    return TransactionData(
        transaction_type=TransactionType.AIRDROP,
        transaction_date=transaction_date,
        asset_code=asset_code,
        amount=amount,
        fiat_value=fiat_value,
        fiat_currency=fiat_currency if fiat_value else None,
    )


def create_staking_income_transaction(
    transaction_date: datetime,
    asset_code: str,
    amount: Decimal,
    fiat_value: Optional[Decimal] = None,
    fiat_currency: str = 'USD',
) -> TransactionData:
    """Create a staking income (CARF502) transaction."""
    return TransactionData(
        transaction_type=TransactionType.STAKING_INCOME,
        transaction_date=transaction_date,
        asset_code=asset_code,
        amount=amount,
        fiat_value=fiat_value,
        fiat_currency=fiat_currency if fiat_value else None,
    )


def create_transfer_out_transaction(
    transaction_date: datetime,
    asset_code: str,
    amount: Decimal,
    destination_address: str,
    to_rcasp: bool = False,
    fiat_value: Optional[Decimal] = None,
    fiat_currency: str = 'USD',
) -> TransactionData:
    """Create a transfer out transaction."""
    txn_type = (
        TransactionType.TRANSFER_TO_RCASP if to_rcasp
        else TransactionType.TRANSFER_TO_NON_RCASP
    )
    return TransactionData(
        transaction_type=txn_type,
        transaction_date=transaction_date,
        asset_code=asset_code,
        amount=amount,
        destination_address=destination_address,
        fiat_value=fiat_value,
        fiat_currency=fiat_currency if fiat_value else None,
    )


def create_mining_transaction(
    transaction_date: datetime,
    asset_code: str,
    amount: Decimal,
    fiat_value: Optional[Decimal] = None,
    fiat_currency: str = 'USD',
) -> TransactionData:
    """Create a mining income (CARF503) transaction."""
    return TransactionData(
        transaction_type=TransactionType.MINING,
        transaction_date=transaction_date,
        asset_code=asset_code,
        amount=amount,
        fiat_value=fiat_value,
        fiat_currency=fiat_currency if fiat_value else None,
    )
