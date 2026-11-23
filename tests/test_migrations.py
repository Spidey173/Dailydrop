"""
Tests for versioned migration runner and seed data management.
Validates:
1. runner.py discovers, records, and applies migrations in schema_migrations table.
2. runner.py execution is idempotent (second run applies zero migrations).
3. seed.py idempotently provisions users and catalog products without duplication.
"""
import pytest
from unittest.mock import patch, MagicMock
from database import get_db_connection
from migrations.runner import run_migrations, get_applied_migrations
from seed import seed_users, seed_products, seed_database


def test_schema_migrations_table_and_retrieval():
    """Verify schema_migrations table exists and returns tracked versions."""
    applied = get_applied_migrations()
    assert isinstance(applied, list)

    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1 FROM schema_migrations LIMIT 1")
            # If query executes without table-not-found error, table exists
            assert cursor is not None


def test_migration_runner_idempotency():
    """Verify that migrations can be executed and subsequent runs report 0 pending migrations."""
    # First execution applies any remaining migrations
    count_first, applied_first = run_migrations()
    assert count_first >= 0

    # Second execution must be an idempotent no-op
    count_second, applied_second = run_migrations()
    assert count_second == 0
    assert applied_second == []


def test_seed_database_idempotent():
    """Verify seed_database creates accounts and products idempotently."""
    seed_database()

    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) as count FROM users WHERE role = 'admin'")
            admin_row = cursor.fetchone()
            admin_count = admin_row['count'] if isinstance(admin_row, dict) else admin_row[0]
            assert admin_count >= 1

            cursor.execute("SELECT COUNT(*) as count FROM users WHERE email = 'demo_dailydrop@gmail.com'")
            demo_row = cursor.fetchone()
            demo_count = demo_row['count'] if isinstance(demo_row, dict) else demo_row[0]
            assert demo_count == 1

            cursor.execute("SELECT COUNT(*) as count FROM products")
            prod_row = cursor.fetchone()
            prod_count = prod_row['count'] if isinstance(prod_row, dict) else prod_row[0]
            assert prod_count > 0

    # Run seed_database a second time; counts must remain stable
    seed_database()
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) as count FROM users WHERE email = 'demo_dailydrop@gmail.com'")
            demo_row2 = cursor.fetchone()
            demo_count2 = demo_row2['count'] if isinstance(demo_row2, dict) else demo_row2[0]
            assert demo_count2 == 1
