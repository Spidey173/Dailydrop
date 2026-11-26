"""
Tests for versioned migration runner and seed data management.
Validates:
1. runner.py discovers, records, and applies migrations in schema_migrations table.
2. runner.py execution is idempotent (second run applies zero migrations).
3. seed.py idempotently provisions users and catalog products without duplication.
"""
from core.database import get_db_connection
from migrations.runner import run_migrations, get_applied_migrations
from seed import seed_database


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


def test_migration_runner_applies_only_pending_migration_on_populated_db():
    """Verify that when 001-006 are marked applied, runner applies only 007 idempotently."""
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            # Temporarily simulate state where 001-006 are applied but 007 is pending
            cursor.execute("DELETE FROM schema_migrations WHERE version = '007_sync_missing_indexes_and_pending_orders_city.sql'")
            for v in [
                '001_initial_schema.sql',
                '002_add_order_items_and_pending_orders.sql',
                '003_add_outbox_events_and_indexes.sql',
                '004_state_machine_and_inventory_checks.sql',
                '005_add_city_and_delivery_duration_to_orders.sql',
                '006_add_claimed_at_to_outbox_events.sql'
            ]:
                cursor.execute("INSERT INTO schema_migrations (version) VALUES (%s) ON CONFLICT (version) DO NOTHING", (v,))

    # Run migrations
    count, applied = run_migrations()
    assert count == 1
    assert applied == ['007_sync_missing_indexes_and_pending_orders_city.sql']

    # Subsequent run must be no-op
    count2, applied2 = run_migrations()
    assert count2 == 0
    assert applied2 == []


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
