#!/usr/bin/env python3
"""
CARFul - Database Initialization Script

Creates and initializes the SQLite database with schema and seed data.
"""

import sqlite3
import os
from pathlib import Path


def init_database(db_path: str = "carful.db") -> sqlite3.Connection:
    """
    Initialize the CARFul database with schema and seed data.

    Args:
        db_path: Path to the SQLite database file

    Returns:
        sqlite3.Connection to the initialized database
    """
    # Get the directory containing this script
    base_dir = Path(__file__).parent

    # Read schema
    schema_path = base_dir / "schema.sql"
    with open(schema_path, "r") as f:
        schema_sql = f.read()

    # Read country codes seed
    seed_path = base_dir / "config" / "country_codes_seed.sql"
    with open(seed_path, "r") as f:
        seed_sql = f.read()

    # Connect to database
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")  # Enable FK constraints

    # Execute schema
    conn.executescript(schema_sql)

    # Check if country codes already seeded
    cursor = conn.execute("SELECT COUNT(*) FROM country_codes")
    count = cursor.fetchone()[0]

    if count == 0:
        # Execute seed data
        conn.executescript(seed_sql)
        print(f"Seeded {conn.execute('SELECT COUNT(*) FROM country_codes').fetchone()[0]} country codes")

    conn.commit()
    return conn


def verify_database(conn: sqlite3.Connection) -> dict:
    """
    Verify database structure and return table info.

    Args:
        conn: SQLite database connection

    Returns:
        Dictionary with table information
    """
    info = {}

    # Get all tables
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    tables = [row[0] for row in cursor.fetchall()]
    info["tables"] = tables

    # Get row counts
    info["row_counts"] = {}
    for table in tables:
        cursor = conn.execute(f'SELECT COUNT(*) FROM "{table}"')
        info["row_counts"][table] = cursor.fetchone()[0]

    # Verify country code constraints work
    info["constraints_working"] = True
    try:
        # Try to insert invalid country code - should fail
        conn.execute(
            "INSERT INTO message_header (sending_comp_auth, receiving_comp_auth, message_type_indic, message_ref_id, reporting_period_start, reporting_period_end, timestamp) VALUES ('XX', 'US', 'CARF701', 'test', '2025-01-01', '2025-12-31', '2025-01-01T00:00:00Z')"
        )
        info["constraints_working"] = False  # Should have failed!
    except sqlite3.IntegrityError:
        pass  # Expected - constraint is working

    return info


if __name__ == "__main__":
    import sys

    db_path = sys.argv[1] if len(sys.argv) > 1 else "carful.db"

    print(f"Initializing CARFul database: {db_path}")
    conn = init_database(db_path)

    print("\nVerifying database structure...")
    info = verify_database(conn)

    print(f"\nTables created: {', '.join(info['tables'])}")
    print("\nRow counts:")
    for table, count in info["row_counts"].items():
        print(f"  {table}: {count}")

    print(f"\nForeign key constraints: {'✓ Working' if info['constraints_working'] else '✗ NOT working'}")

    conn.close()
    print(f"\n✓ Database initialized successfully: {db_path}")
