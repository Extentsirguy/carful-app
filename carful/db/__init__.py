"""
CARFul Database Module

Provides database operations for CARF XML generation:
    - user_generator: Streaming reads of users with transactions
    - Connection management and query utilities
"""

from .user_generator import (
    UserGenerator,
    UserRecord,
    TransactionRecord,
    ControllingPersonRecord,
    DatabaseConfig,
    get_user_count,
    get_transaction_count,
)

__all__ = [
    'UserGenerator',
    'UserRecord',
    'TransactionRecord',
    'ControllingPersonRecord',
    'DatabaseConfig',
    'get_user_count',
    'get_transaction_count',
]
