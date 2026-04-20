"""
CARFul - CARF Transaction Type Enumerations

This module defines the OECD CARF transaction type codes as Python Enums.
These codes are used to classify crypto-asset transactions for regulatory reporting.

Reference: OECD CARF XML Schema v2.0 (July 2025)
"""

from enum import Enum
from typing import Optional


class TransactionCategory(str, Enum):
    """
    High-level transaction categories in CARF reporting.
    """
    EXCHANGE = "Exchange"           # Crypto-to-crypto or crypto-to-fiat exchanges
    TRANSFER_IN = "TransferIn"      # Inbound transfers of crypto-assets
    TRANSFER_OUT = "TransferOut"    # Outbound transfers of crypto-assets
    RETAIL_PAYMENT = "RetailPayment"  # Retail payment transactions


class ExchangeType(str, Enum):
    """
    CARF Exchange Transaction Types (CARF4xx series).

    Used to provide additional information on exchange transactions
    involving crypto-to-crypto or crypto-to-fiat conversions.
    """
    CARF401 = "CARF401"  # Staking
    CARF402 = "CARF402"  # Crypto Loan
    CARF403 = "CARF403"  # Wrapping
    CARF404 = "CARF404"  # Collateral

    @property
    def description(self) -> str:
        """Human-readable description of the exchange type."""
        descriptions = {
            "CARF401": "Staking",
            "CARF402": "Crypto Loan",
            "CARF403": "Wrapping",
            "CARF404": "Collateral",
        }
        return descriptions.get(self.value, "Unknown")


class TransferInType(str, Enum):
    """
    CARF Transfer In Types (CARF5xx series).

    Used to classify inbound transfers of crypto-assets.
    """
    CARF501 = "CARF501"  # Airdrop
    CARF502 = "CARF502"  # Staking Income
    CARF503 = "CARF503"  # Mining Income
    CARF504 = "CARF504"  # Crypto Loan (received)
    CARF505 = "CARF505"  # Transfer from another RCASP
    CARF506 = "CARF506"  # Sale of Goods/Services
    CARF507 = "CARF507"  # Collateral (received)
    CARF508 = "CARF508"  # Other
    CARF509 = "CARF509"  # Unknown (default)

    @property
    def description(self) -> str:
        """Human-readable description of the transfer in type."""
        descriptions = {
            "CARF501": "Airdrop",
            "CARF502": "Staking Income",
            "CARF503": "Mining Income",
            "CARF504": "Crypto Loan (received)",
            "CARF505": "Transfer from another RCASP",
            "CARF506": "Sale of Goods/Services",
            "CARF507": "Collateral (received)",
            "CARF508": "Other",
            "CARF509": "Unknown",
        }
        return descriptions.get(self.value, "Unknown")


class TransferOutType(str, Enum):
    """
    CARF Transfer Out Types (CARF6xx series).

    Used to classify outbound transfers of crypto-assets.
    """
    CARF601 = "CARF601"  # Transfer to another RCASP
    CARF602 = "CARF602"  # Crypto Loan (given)
    CARF603 = "CARF603"  # Purchase of Goods/Services
    CARF604 = "CARF604"  # Collateral (posted)
    CARF605 = "CARF605"  # Other
    CARF606 = "CARF606"  # Unknown (default)

    @property
    def description(self) -> str:
        """Human-readable description of the transfer out type."""
        descriptions = {
            "CARF601": "Transfer to another RCASP",
            "CARF602": "Crypto Loan (given)",
            "CARF603": "Purchase of Goods/Services",
            "CARF604": "Collateral (posted)",
            "CARF605": "Other",
            "CARF606": "Unknown",
        }
        return descriptions.get(self.value, "Unknown")


class MessageTypeIndicator(str, Enum):
    """
    CARF Message Type Indicators (CARF7xx series).

    Used in MessageHeader to indicate the type of CARF message.
    """
    CARF701 = "CARF701"  # New data submission
    CARF702 = "CARF702"  # Corrections/deletions
    CARF703 = "CARF703"  # Nil report (no data to report)

    @property
    def description(self) -> str:
        """Human-readable description of the message type."""
        descriptions = {
            "CARF701": "New data submission",
            "CARF702": "Corrections/deletions for previously sent data",
            "CARF703": "Nil report (no data to report)",
        }
        return descriptions.get(self.value, "Unknown")


class NexusType(str, Enum):
    """
    CARF Nexus Types (CARF8xx series).

    Used to indicate the basis for RCASP reporting obligation.
    """
    CARF801 = "CARF801"  # Jurisdiction of tax residence
    CARF802 = "CARF802"  # Jurisdiction of incorporation
    CARF803 = "CARF803"  # Jurisdiction of management
    CARF804 = "CARF804"  # Jurisdiction of regular place of business
    CARF805 = "CARF805"  # Other nexus

    @property
    def description(self) -> str:
        """Human-readable description of the nexus type."""
        descriptions = {
            "CARF801": "Jurisdiction of tax residence",
            "CARF802": "Jurisdiction of incorporation",
            "CARF803": "Jurisdiction of management",
            "CARF804": "Jurisdiction of regular place of business",
            "CARF805": "Other nexus",
        }
        return descriptions.get(self.value, "Unknown")


class DocTypeIndicator(str, Enum):
    """
    Document Type Indicators (OECD standard).

    Used in DocSpec to indicate whether data is new, corrected, or deleted.
    """
    OECD1 = "OECD1"  # New data
    OECD2 = "OECD2"  # Correction
    OECD3 = "OECD3"  # Deletion

    @property
    def description(self) -> str:
        """Human-readable description of the document type."""
        descriptions = {
            "OECD1": "New data",
            "OECD2": "Correction to previously submitted data",
            "OECD3": "Deletion of previously submitted data",
        }
        return descriptions.get(self.value, "Unknown")


# Combined set of all valid transaction type codes
ALL_TRANSACTION_TYPES: frozenset[str] = frozenset(
    [e.value for e in ExchangeType]
    + [e.value for e in TransferInType]
    + [e.value for e in TransferOutType]
)

# Mapping from transaction type to category
TRANSACTION_TYPE_TO_CATEGORY: dict[str, TransactionCategory] = {
    # Exchange types
    **{e.value: TransactionCategory.EXCHANGE for e in ExchangeType},
    # Transfer In types
    **{e.value: TransactionCategory.TRANSFER_IN for e in TransferInType},
    # Transfer Out types
    **{e.value: TransactionCategory.TRANSFER_OUT for e in TransferOutType},
}


def is_valid_transaction_type(code: str) -> bool:
    """
    Check if a transaction type code is valid.

    Args:
        code: The CARF transaction type code

    Returns:
        True if valid, False otherwise
    """
    return code in ALL_TRANSACTION_TYPES


def get_transaction_category(code: str) -> Optional[TransactionCategory]:
    """
    Get the transaction category for a given CARF code.

    Args:
        code: The CARF transaction type code

    Returns:
        TransactionCategory or None if invalid
    """
    return TRANSACTION_TYPE_TO_CATEGORY.get(code)


def get_transaction_description(code: str) -> Optional[str]:
    """
    Get the human-readable description for a transaction type code.

    Args:
        code: The CARF transaction type code

    Returns:
        Description string or None if invalid
    """
    # Try each enum type
    for enum_class in [ExchangeType, TransferInType, TransferOutType]:
        try:
            return enum_class(code).description
        except ValueError:
            continue
    return None


def get_all_codes_by_category() -> dict[TransactionCategory, list[str]]:
    """
    Get all transaction codes organized by category.

    Returns:
        Dictionary mapping categories to lists of codes
    """
    return {
        TransactionCategory.EXCHANGE: [e.value for e in ExchangeType],
        TransactionCategory.TRANSFER_IN: [e.value for e in TransferInType],
        TransactionCategory.TRANSFER_OUT: [e.value for e in TransferOutType],
    }


if __name__ == "__main__":
    # Print all codes for reference
    print("CARF Transaction Type Codes")
    print("=" * 50)

    for category, codes in get_all_codes_by_category().items():
        print(f"\n{category.value}:")
        for code in codes:
            desc = get_transaction_description(code)
            print(f"  {code}: {desc}")
