"""
CARFul - Transaction Keyword Mapper

This module provides heuristic keyword-based mapping from CSV transaction
descriptions to CARF transaction type codes.

The mapper analyzes transaction description fields and suggests appropriate
CARF codes based on keyword patterns commonly found in crypto exchange exports.

Reference: OECD CARF XML Schema v2.0 (July 2025)
"""

import re
from dataclasses import dataclass
from typing import Optional
from enum import Enum

from enumerations import (
    TransactionCategory,
    ExchangeType,
    TransferInType,
    TransferOutType,
    get_transaction_description,
)


class MappingConfidence(str, Enum):
    """Confidence level of the keyword mapping."""
    HIGH = "high"        # Multiple strong keyword matches
    MEDIUM = "medium"    # Single strong keyword or multiple weak matches
    LOW = "low"          # Weak keyword match, needs user review
    UNKNOWN = "unknown"  # No keywords matched, defaulting to Unknown type


@dataclass
class MappingResult:
    """Result of keyword-based transaction mapping."""
    transaction_type: str           # CARF code (e.g., "CARF401")
    category: TransactionCategory   # Transaction category
    confidence: MappingConfidence   # Confidence level
    matched_keywords: list[str]     # Keywords that triggered the match
    description: str                # Human-readable type description
    suggested: bool = True          # True = suggested, False = confirmed by user

    def __str__(self) -> str:
        return (
            f"{self.transaction_type} ({self.description}) - "
            f"{self.confidence.value} confidence"
        )


# Keyword patterns for each transaction type
# Format: {CARF_CODE: (keywords, weight)}
# Weight: 2 = strong indicator, 1 = weak indicator

KEYWORD_PATTERNS: dict[str, tuple[list[str], int]] = {
    # =========================================================================
    # Exchange Types (CARF4xx)
    # =========================================================================
    "CARF401": (  # Staking
        [
            "stake", "staking", "staked", "unstake", "unstaking",
            "validator", "delegation", "delegate", "delegated",
            "bonding", "unbonding", "epoch", "slot",
        ],
        2,
    ),
    "CARF402": (  # Crypto Loan
        [
            "loan", "lend", "lending", "borrow", "borrowed",
            "borrowing", "interest", "repay", "repayment",
            "defi loan", "flash loan", "liquidate",
        ],
        2,
    ),
    "CARF403": (  # Wrapping
        [
            "wrap", "wrapped", "unwrap", "unwrapped", "wrapping",
            "weth", "wbtc", "wmatic", "wavax",
            "bridge", "bridged", "bridging", "cross-chain",
            "layer2", "l2", "rollup",
        ],
        2,
    ),
    "CARF404": (  # Collateral
        [
            "collateral", "margin", "leverage", "leveraged",
            "liquidation", "liquidated", "margin call",
            "deposit margin", "withdraw margin",
        ],
        2,
    ),
    # =========================================================================
    # Transfer In Types (CARF5xx)
    # =========================================================================
    "CARF501": (  # Airdrop
        [
            "airdrop", "air drop", "drop", "giveaway",
            "distribution", "claim", "claimed", "claimable",
            "free", "bonus", "promotional", "promo",
            "retroactive", "retro",
        ],
        2,
    ),
    "CARF502": (  # Staking Income
        [
            "staking reward", "staking income", "stake reward",
            "validator reward", "delegation reward",
            "epoch reward", "block reward", "slot reward",
            "yield", "apr", "apy",
        ],
        2,
    ),
    "CARF503": (  # Mining Income
        [
            "mining", "mined", "miner", "mine reward",
            "hashrate", "pow reward",
            "proof of work", "coinbase reward", "coinbase transaction",
        ],
        2,
    ),
    "CARF504": (  # Crypto Loan (received)
        [
            "loan received", "borrowed", "borrow",
            "loan deposit", "credit", "lending received",
        ],
        1,  # Lower weight - context dependent
    ),
    "CARF505": (  # Transfer from another RCASP
        [
            "transfer from", "received from", "incoming transfer",
            "deposit from exchange", "from binance", "from coinbase",
            "from kraken", "from gemini", "from ftx", "from kucoin",
            "from bitstamp", "from bitfinex", "from huobi", "from okx",
        ],
        2,  # Higher weight for exchange transfers
    ),
    "CARF506": (  # Sale of Goods/Services (received payment)
        [
            "payment received", "merchant", "invoice",
            "sale", "sold goods", "service payment",
            "pos", "point of sale", "customer payment",
        ],
        2,
    ),
    "CARF507": (  # Collateral (received)
        [
            "collateral received", "collateral deposit",
            "margin deposit", "security deposit",
        ],
        1,
    ),
    "CARF508": (  # Other
        [
            "other income", "miscellaneous", "misc",
            "adjustment", "correction", "refund",
        ],
        1,
    ),
    # =========================================================================
    # Transfer Out Types (CARF6xx)
    # =========================================================================
    "CARF601": (  # Transfer to another RCASP
        [
            "transfer to", "sent to", "outgoing transfer",
            "withdrawal to exchange", "to binance", "to coinbase",
            "to kraken", "to gemini", "to kucoin",
        ],
        1,
    ),
    "CARF602": (  # Crypto Loan (given)
        [
            "loan given", "lent", "lending",
            "loan withdrawal", "loan out",
        ],
        1,
    ),
    "CARF603": (  # Purchase of Goods/Services
        [
            "purchase", "payment", "pay", "paid",
            "buy goods", "merchant payment", "pos payment",
            "subscription", "fee payment",
        ],
        2,
    ),
    "CARF604": (  # Collateral (posted)
        [
            "collateral posted", "collateral sent",
            "margin sent", "security posted",
        ],
        1,
    ),
    "CARF605": (  # Other
        [
            "other expense", "other withdrawal",
            "miscellaneous out", "adjustment out",
        ],
        1,
    ),
}

# Additional context patterns for direction detection
INBOUND_INDICATORS = [
    "receive", "received", "incoming", "deposit", "deposited",
    "credit", "credited", "in", "income", "+",
]

OUTBOUND_INDICATORS = [
    "send", "sent", "outgoing", "withdraw", "withdrawal",
    "debit", "debited", "out", "expense", "-",
]


def normalize_text(text: str) -> str:
    """
    Normalize text for keyword matching.

    Args:
        text: Raw transaction description

    Returns:
        Normalized lowercase text
    """
    if not text:
        return ""

    # Convert to lowercase
    text = text.lower()

    # Replace common separators with spaces
    text = re.sub(r"[_\-/\\|]", " ", text)

    # Remove extra whitespace
    text = " ".join(text.split())

    return text


def detect_direction(text: str) -> Optional[str]:
    """
    Detect if transaction is inbound or outbound based on text.

    Args:
        text: Normalized transaction description

    Returns:
        "in", "out", or None if undetermined
    """
    inbound_score = sum(1 for kw in INBOUND_INDICATORS if kw in text)
    outbound_score = sum(1 for kw in OUTBOUND_INDICATORS if kw in text)

    if inbound_score > outbound_score:
        return "in"
    elif outbound_score > inbound_score:
        return "out"
    return None


def map_transaction(
    description: str,
    amount: Optional[float] = None,
    additional_context: Optional[str] = None,
) -> MappingResult:
    """
    Map a transaction description to a CARF transaction type.

    This function analyzes the description text using keyword patterns
    and returns a suggested CARF code with confidence level.

    Args:
        description: Transaction description from CSV
        amount: Transaction amount (positive = in, negative = out)
        additional_context: Additional fields like "type" or "category"

    Returns:
        MappingResult with suggested CARF code and confidence
    """
    # Normalize all input text
    text = normalize_text(description)
    if additional_context:
        text = f"{text} {normalize_text(additional_context)}"

    # Detect direction from amount if available
    direction = None
    if amount is not None:
        direction = "in" if amount > 0 else "out"

    # If no amount, try to detect from text
    if direction is None:
        direction = detect_direction(text)

    # Score each transaction type
    scores: dict[str, tuple[int, list[str]]] = {}

    for carf_code, (keywords, weight) in KEYWORD_PATTERNS.items():
        matched = []
        for keyword in keywords:
            if keyword in text:
                matched.append(keyword)

        if matched:
            # Apply weight and count
            score = len(matched) * weight
            scores[carf_code] = (score, matched)

    # Find best match
    if scores:
        best_code = max(scores.keys(), key=lambda k: scores[k][0])
        best_score, matched_keywords = scores[best_code]

        # Determine confidence
        if best_score >= 4:
            confidence = MappingConfidence.HIGH
        elif best_score >= 2:
            confidence = MappingConfidence.MEDIUM
        else:
            confidence = MappingConfidence.LOW

        # Get category and description
        category = _get_category_for_code(best_code)
        desc = get_transaction_description(best_code) or "Unknown"

        return MappingResult(
            transaction_type=best_code,
            category=category,
            confidence=confidence,
            matched_keywords=matched_keywords,
            description=desc,
            suggested=True,
        )

    # No match found - default based on direction
    if direction == "in":
        return MappingResult(
            transaction_type=TransferInType.CARF509.value,
            category=TransactionCategory.TRANSFER_IN,
            confidence=MappingConfidence.UNKNOWN,
            matched_keywords=[],
            description="Unknown (inbound)",
            suggested=True,
        )
    elif direction == "out":
        return MappingResult(
            transaction_type=TransferOutType.CARF606.value,
            category=TransactionCategory.TRANSFER_OUT,
            confidence=MappingConfidence.UNKNOWN,
            matched_keywords=[],
            description="Unknown (outbound)",
            suggested=True,
        )
    else:
        # Complete unknown
        return MappingResult(
            transaction_type=TransferInType.CARF509.value,
            category=TransactionCategory.TRANSFER_IN,
            confidence=MappingConfidence.UNKNOWN,
            matched_keywords=[],
            description="Unknown",
            suggested=True,
        )


def _get_category_for_code(code: str) -> TransactionCategory:
    """Get the transaction category for a CARF code."""
    if code.startswith("CARF4"):
        return TransactionCategory.EXCHANGE
    elif code.startswith("CARF5"):
        return TransactionCategory.TRANSFER_IN
    elif code.startswith("CARF6"):
        return TransactionCategory.TRANSFER_OUT
    return TransactionCategory.TRANSFER_IN  # Default


def map_batch(
    transactions: list[dict],
    description_field: str = "description",
    amount_field: Optional[str] = None,
    context_field: Optional[str] = None,
) -> list[tuple[dict, MappingResult]]:
    """
    Map a batch of transactions to CARF types.

    Args:
        transactions: List of transaction dictionaries
        description_field: Field name containing description
        amount_field: Optional field name containing amount
        context_field: Optional field for additional context

    Returns:
        List of (transaction, MappingResult) tuples
    """
    results = []

    for tx in transactions:
        description = tx.get(description_field, "")
        amount = tx.get(amount_field) if amount_field else None
        context = tx.get(context_field) if context_field else None

        result = map_transaction(description, amount, context)
        results.append((tx, result))

    return results


def get_mapping_statistics(results: list[MappingResult]) -> dict:
    """
    Calculate statistics on mapping results.

    Args:
        results: List of MappingResult objects

    Returns:
        Dictionary with statistics
    """
    total = len(results)
    if total == 0:
        return {"total": 0}

    stats = {
        "total": total,
        "by_confidence": {
            MappingConfidence.HIGH.value: 0,
            MappingConfidence.MEDIUM.value: 0,
            MappingConfidence.LOW.value: 0,
            MappingConfidence.UNKNOWN.value: 0,
        },
        "by_category": {},
        "by_type": {},
    }

    for result in results:
        # Count by confidence
        stats["by_confidence"][result.confidence.value] += 1

        # Count by category
        cat = result.category.value
        stats["by_category"][cat] = stats["by_category"].get(cat, 0) + 1

        # Count by type
        stats["by_type"][result.transaction_type] = (
            stats["by_type"].get(result.transaction_type, 0) + 1
        )

    # Calculate percentages
    high_medium = (
        stats["by_confidence"]["high"] + stats["by_confidence"]["medium"]
    )
    stats["accuracy_estimate"] = round(high_medium / total * 100, 1)

    return stats


if __name__ == "__main__":
    # Test examples
    test_descriptions = [
        "Staking reward for ETH validator",
        "Received airdrop tokens",
        "Wrapped ETH to WETH",
        "Mining reward - BTC",
        "Payment for goods",
        "Transfer from Coinbase",
        "Loan interest received",
        "Random transaction xyz",
    ]

    print("CARFul Transaction Mapper Test")
    print("=" * 60)

    for desc in test_descriptions:
        result = map_transaction(desc)
        print(f"\n'{desc}'")
        print(f"  → {result}")
        if result.matched_keywords:
            print(f"    Keywords: {', '.join(result.matched_keywords)}")
