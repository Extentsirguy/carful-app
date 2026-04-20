"""
CARFul - User Generator for Streaming Database Reads

Provides generator-based database reading for efficient XML generation.
Yields users with their transactions in batches to maintain O(1) memory
footprint during large-scale XML generation.

Features:
    - Batch processing (configurable batch size)
    - Lazy loading of transactions per user
    - Memory-efficient iteration
    - Support for filtering by RCASP

Usage:
    from db.user_generator import UserGenerator

    gen = UserGenerator('database.db', batch_size=1000)
    for user_record in gen.iter_users():
        # user_record contains user data + transactions
        process_user(user_record)

    # Or with RCASP filtering
    for user in gen.iter_users_for_rcasp(rcasp_id=1):
        process_user(user)
"""

import json
import sqlite3
from datetime import datetime, date
from decimal import Decimal
from typing import Generator, List, Optional, Dict, Any, Iterator
from dataclasses import dataclass, field
from pathlib import Path


# =============================================================================
# Data Records
# =============================================================================

@dataclass
class TransactionRecord:
    """
    Transaction data from database.

    Maps to the 'transaction' table schema.
    """
    id: int
    user_id: int
    transaction_category: str
    transaction_type: str  # CARF4xx-6xx codes
    asset_type: str
    asset_name: Optional[str]
    amount: Decimal
    amount_fiat: Optional[Decimal]
    fiat_currency: Optional[str]
    transaction_id: Optional[str]  # Blockchain/exchange ID
    timestamp: datetime

    # Exchange-specific fields
    acquired_asset_type: Optional[str] = None
    acquired_amount: Optional[Decimal] = None
    disposed_asset_type: Optional[str] = None
    disposed_amount: Optional[Decimal] = None

    # Aggregation
    is_aggregated: bool = False
    aggregation_count: int = 1

    # Source tracking
    source_row: Optional[int] = None
    source_file: Optional[str] = None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> 'TransactionRecord':
        """Create TransactionRecord from database row."""
        return cls(
            id=row['id'],
            user_id=row['user_id'],
            transaction_category=row['transaction_category'],
            transaction_type=row['transaction_type'],
            asset_type=row['asset_type'],
            asset_name=row['asset_name'],
            amount=Decimal(row['amount']) if row['amount'] else Decimal('0'),
            amount_fiat=Decimal(row['amount_fiat']) if row['amount_fiat'] else None,
            fiat_currency=row['fiat_currency'],
            transaction_id=row['transaction_id'],
            timestamp=datetime.fromisoformat(row['timestamp'].replace('Z', '+00:00')),
            acquired_asset_type=row['acquired_asset_type'],
            acquired_amount=Decimal(row['acquired_amount']) if row['acquired_amount'] else None,
            disposed_asset_type=row['disposed_asset_type'],
            disposed_amount=Decimal(row['disposed_amount']) if row['disposed_amount'] else None,
            is_aggregated=bool(row['is_aggregated']),
            aggregation_count=row['aggregation_count'] or 1,
            source_row=row['source_row'],
            source_file=row['source_file'],
        )


@dataclass
class ControllingPersonRecord:
    """
    Controlling person data for entity users.

    Maps to the 'controlling_person' table schema.
    """
    id: int
    user_id: int
    first_name: str
    last_name: str
    middle_name: Optional[str] = None
    tin: Optional[str] = None
    tin_unknown: bool = False
    tin_issued_by: Optional[str] = None
    tax_residency: Optional[str] = None
    address_json: Optional[str] = None
    address_country: Optional[str] = None
    birth_date: Optional[date] = None
    birth_city: Optional[str] = None
    birth_country: Optional[str] = None
    control_type: Optional[str] = None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> 'ControllingPersonRecord':
        """Create ControllingPersonRecord from database row."""
        birth_dt = None
        if row['birth_date']:
            try:
                birth_dt = date.fromisoformat(row['birth_date'])
            except ValueError:
                pass

        return cls(
            id=row['id'],
            user_id=row['user_id'],
            first_name=row['first_name'],
            last_name=row['last_name'],
            middle_name=row['middle_name'],
            tin=row['tin'],
            tin_unknown=bool(row['tin_unknown']),
            tin_issued_by=row['tin_issued_by'],
            tax_residency=row['tax_residency'],
            address_json=row['address_json'],
            address_country=row['address_country'],
            birth_date=birth_dt,
            birth_city=row['birth_city'],
            birth_country=row['birth_country'],
            control_type=row['control_type'],
        )

    @property
    def address(self) -> Optional[Dict[str, Any]]:
        """Parse address JSON."""
        if self.address_json:
            try:
                return json.loads(self.address_json)
            except json.JSONDecodeError:
                return None
        return None


@dataclass
class UserRecord:
    """
    User record with transactions and controlling persons.

    Combines data from 'user', 'transaction', and 'controlling_person' tables.
    """
    # Core identification
    id: int
    rcasp_id: int
    user_type: str  # 'Individual' or 'Entity'
    doc_type_indic: str
    doc_ref_id: str
    corr_doc_ref_id: Optional[str] = None

    # Individual fields
    first_name: Optional[str] = None
    middle_name: Optional[str] = None
    last_name: Optional[str] = None

    # Entity fields
    entity_name: Optional[str] = None

    # Tax information
    tin: Optional[str] = None
    tin_unknown: bool = False
    tin_issued_by: Optional[str] = None
    tax_residency: str = ''

    # Address
    address_json: Optional[str] = None
    address_country: Optional[str] = None

    # Birth info (individuals)
    birth_date: Optional[date] = None
    birth_city: Optional[str] = None
    birth_country: Optional[str] = None

    # Account
    account_number: Optional[str] = None
    account_number_type: Optional[str] = None

    # Related records (loaded lazily)
    transactions: List[TransactionRecord] = field(default_factory=list)
    controlling_persons: List[ControllingPersonRecord] = field(default_factory=list)

    # Source tracking
    source_row: Optional[int] = None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> 'UserRecord':
        """Create UserRecord from database row (without transactions)."""
        birth_dt = None
        if row['birth_date']:
            try:
                birth_dt = date.fromisoformat(row['birth_date'])
            except ValueError:
                pass

        return cls(
            id=row['id'],
            rcasp_id=row['rcasp_id'],
            user_type=row['user_type'],
            doc_type_indic=row['doc_type_indic'],
            doc_ref_id=row['doc_ref_id'],
            corr_doc_ref_id=row['corr_doc_ref_id'],
            first_name=row['first_name'],
            middle_name=row['middle_name'],
            last_name=row['last_name'],
            entity_name=row['entity_name'],
            tin=row['tin'],
            tin_unknown=bool(row['tin_unknown']),
            tin_issued_by=row['tin_issued_by'],
            tax_residency=row['tax_residency'],
            address_json=row['address_json'],
            address_country=row['address_country'],
            birth_date=birth_dt,
            birth_city=row['birth_city'],
            birth_country=row['birth_country'],
            account_number=row['account_number'],
            account_number_type=row['account_number_type'],
            source_row=row['source_row'],
        )

    @property
    def is_individual(self) -> bool:
        """Check if user is an individual."""
        return self.user_type == 'Individual'

    @property
    def is_entity(self) -> bool:
        """Check if user is an entity."""
        return self.user_type == 'Entity'

    @property
    def display_name(self) -> str:
        """Get display name for user."""
        if self.is_individual:
            parts = [self.first_name, self.middle_name, self.last_name]
            return ' '.join(p for p in parts if p)
        return self.entity_name or ''

    @property
    def address(self) -> Optional[Dict[str, Any]]:
        """Parse address JSON."""
        if self.address_json:
            try:
                return json.loads(self.address_json)
            except json.JSONDecodeError:
                return None
        return None

    @property
    def has_controlling_persons(self) -> bool:
        """Check if entity has controlling persons."""
        return len(self.controlling_persons) > 0


# =============================================================================
# Configuration
# =============================================================================

@dataclass
class DatabaseConfig:
    """Configuration for UserGenerator."""
    batch_size: int = 1000  # Users per batch
    include_transactions: bool = True
    include_controlling_persons: bool = True
    order_by: str = 'id'  # Column to order users by


# =============================================================================
# User Generator
# =============================================================================

class UserGenerator:
    """
    Generator for streaming users with transactions from SQLite database.

    Yields UserRecord objects with their associated transactions in batches
    to maintain O(1) memory footprint during large-scale XML generation.

    Example:
        gen = UserGenerator('carf.db', batch_size=1000)

        # Iterate all users
        for user in gen.iter_users():
            xml_element = user_builder.build(user)
            writer.write_element(xml_element)

        # Filter by RCASP
        for user in gen.iter_users_for_rcasp(rcasp_id=1):
            process_user(user)

        # Get counts for progress reporting
        total_users = gen.get_user_count()
        total_txns = gen.get_transaction_count()
    """

    def __init__(
        self,
        db_path: str | Path,
        config: Optional[DatabaseConfig] = None,
    ):
        """
        Initialize UserGenerator.

        Args:
            db_path: Path to SQLite database
            config: Generator configuration
        """
        self.db_path = Path(db_path)
        self.config = config or DatabaseConfig()
        self._conn: Optional[sqlite3.Connection] = None

    def _get_connection(self) -> sqlite3.Connection:
        """Get or create database connection."""
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def close(self) -> None:
        """Close database connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> 'UserGenerator':
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.close()

    def get_user_count(self, rcasp_id: Optional[int] = None) -> int:
        """Get total number of users."""
        conn = self._get_connection()
        if rcasp_id is not None:
            cursor = conn.execute(
                'SELECT COUNT(*) FROM user WHERE rcasp_id = ?',
                (rcasp_id,)
            )
        else:
            cursor = conn.execute('SELECT COUNT(*) FROM user')
        return cursor.fetchone()[0]

    def get_transaction_count(
        self,
        rcasp_id: Optional[int] = None,
        user_id: Optional[int] = None,
    ) -> int:
        """Get total number of transactions."""
        conn = self._get_connection()

        if user_id is not None:
            cursor = conn.execute(
                'SELECT COUNT(*) FROM "transaction" WHERE user_id = ?',
                (user_id,)
            )
        elif rcasp_id is not None:
            cursor = conn.execute(
                '''SELECT COUNT(*) FROM "transaction" t
                   JOIN user u ON t.user_id = u.id
                   WHERE u.rcasp_id = ?''',
                (rcasp_id,)
            )
        else:
            cursor = conn.execute('SELECT COUNT(*) FROM "transaction"')

        return cursor.fetchone()[0]

    def _load_transactions(self, user_id: int) -> List[TransactionRecord]:
        """Load transactions for a user."""
        conn = self._get_connection()
        cursor = conn.execute(
            '''SELECT * FROM "transaction"
               WHERE user_id = ?
               ORDER BY timestamp''',
            (user_id,)
        )
        return [TransactionRecord.from_row(row) for row in cursor]

    def _load_controlling_persons(self, user_id: int) -> List[ControllingPersonRecord]:
        """Load controlling persons for an entity user."""
        conn = self._get_connection()
        cursor = conn.execute(
            'SELECT * FROM controlling_person WHERE user_id = ?',
            (user_id,)
        )
        return [ControllingPersonRecord.from_row(row) for row in cursor]

    def _enrich_user(self, user: UserRecord) -> UserRecord:
        """Enrich user with transactions and controlling persons."""
        if self.config.include_transactions:
            user.transactions = self._load_transactions(user.id)

        if self.config.include_controlling_persons and user.is_entity:
            user.controlling_persons = self._load_controlling_persons(user.id)

        return user

    def iter_users(
        self,
        rcasp_id: Optional[int] = None,
    ) -> Generator[UserRecord, None, None]:
        """
        Iterate over users with their transactions.

        Yields users in batches based on config.batch_size.
        Each user is enriched with transactions before yielding.

        Args:
            rcasp_id: Optional RCASP ID to filter users

        Yields:
            UserRecord with transactions and controlling persons
        """
        conn = self._get_connection()

        # Build query
        if rcasp_id is not None:
            query = f'''SELECT * FROM user
                       WHERE rcasp_id = ?
                       ORDER BY {self.config.order_by}'''
            params = (rcasp_id,)
        else:
            query = f'SELECT * FROM user ORDER BY {self.config.order_by}'
            params = ()

        cursor = conn.execute(query, params)

        # Stream users in batches
        while True:
            rows = cursor.fetchmany(self.config.batch_size)
            if not rows:
                break

            for row in rows:
                user = UserRecord.from_row(row)
                user = self._enrich_user(user)
                yield user

    def iter_users_for_rcasp(self, rcasp_id: int) -> Generator[UserRecord, None, None]:
        """
        Iterate over users for a specific RCASP.

        Args:
            rcasp_id: RCASP ID to filter users

        Yields:
            UserRecord with transactions
        """
        yield from self.iter_users(rcasp_id=rcasp_id)

    def iter_user_batches(
        self,
        rcasp_id: Optional[int] = None,
    ) -> Generator[List[UserRecord], None, None]:
        """
        Iterate over users in batches.

        Yields lists of users (batch_size users per list).
        Useful for bulk processing.

        Args:
            rcasp_id: Optional RCASP ID to filter

        Yields:
            List of UserRecord objects
        """
        batch: List[UserRecord] = []

        for user in self.iter_users(rcasp_id=rcasp_id):
            batch.append(user)

            if len(batch) >= self.config.batch_size:
                yield batch
                batch = []

        # Yield remaining
        if batch:
            yield batch


# =============================================================================
# Convenience Functions
# =============================================================================

def get_user_count(db_path: str | Path, rcasp_id: Optional[int] = None) -> int:
    """Get user count from database."""
    with UserGenerator(db_path) as gen:
        return gen.get_user_count(rcasp_id)


def get_transaction_count(
    db_path: str | Path,
    rcasp_id: Optional[int] = None,
    user_id: Optional[int] = None,
) -> int:
    """Get transaction count from database."""
    with UserGenerator(db_path) as gen:
        return gen.get_transaction_count(rcasp_id, user_id)
