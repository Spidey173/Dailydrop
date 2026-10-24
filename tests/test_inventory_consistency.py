"""
Tests for inventory consistency between Redis cache and PostgreSQL database.
Validates:
1. PostgreSQL is the authoritative single source of truth (SSOT).
2. Failure between Redis decrement and DB commit rolls back Redis cache cleanly.
3. Database constraint / abort triggers Redis compensation rollback.
4. Active reconciliation re-aligns drifted Redis cache values to match PostgreSQL.
"""
import pytest
from unittest.mock import patch, MagicMock
from app import create_app
from database import get_db_connection
from services.redis_service import RedisService
from services.inventory_reservation_service import InventoryReservationService
from services.order_service import OrderService


@pytest.fixture
def app_client():
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        with app.app_context():
            yield client


def test_failure_between_cache_mutation_and_db_commit_rolls_back_cache(app_client):
    """
    Simulate a scenario where Redis cache is decremented, but a downstream failure
    (e.g., DB serialization failure, crash, or constraint violation) happens before commit.
    Verify Redis stock is compensated/rolled back to match the DB truth.
    """
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT product_id, stock FROM products WHERE stock >= 10 LIMIT 1")
            prod = cursor.fetchone()
            pid = prod['product_id'] if isinstance(prod, dict) else prod[0]
            initial_stock = prod['stock'] if isinstance(prod, dict) else prod[1]

    # Pre-warm Redis cache with current database authoritative stock
    RedisService.set_stock(pid, initial_stock)
    assert RedisService.get_stock(pid) == initial_stock

    # Attempt checkout with mock failure during OrderPersistenceService.persist_order
    cart = [{"product_id": pid, "quantity": 3}]
    with patch("services.order_persistence_service.OrderPersistenceService.persist_order", side_effect=Exception("Database connection crash before commit")):
        success, msg, order_id = OrderService.create_order(
            user_id=1,
            full_name="Crash Tester",
            phone_number="9876543210",
            address="Test Lane",
            products=cart,
            total_amount=100.0
        )
        assert success is False
        assert order_id is None

    # Verify PostgreSQL DB stock was never mutated / remained unchanged
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT stock FROM products WHERE product_id = %s", (pid,))
            db_row = cursor.fetchone()
            db_stock = db_row['stock'] if isinstance(db_row, dict) else db_row[0]
            assert db_stock == initial_stock

    # Verify Redis cache was compensated and equals PostgreSQL source of truth
    cached_stock = RedisService.get_stock(pid)
    assert cached_stock == initial_stock


def test_insufficient_stock_in_db_causes_redis_compensation(app_client):
    """
    If Redis allows decrement (e.g. stale cache had 10 units, but DB only has 2 units),
    the PostgreSQL conditional UPDATE (stock >= req) will fail (rowcount == 0).
    The system must abort transaction and rollback the Redis decrement.
    """
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT product_id, stock FROM products WHERE stock >= 5 LIMIT 1")
            prod = cursor.fetchone()
            pid = prod['product_id'] if isinstance(prod, dict) else prod[0]
            actual_db_stock = prod['stock'] if isinstance(prod, dict) else prod[1]

    # Artificially set Redis higher than DB stock
    stale_high_redis_stock = actual_db_stock + 10
    RedisService.set_stock(pid, stale_high_redis_stock)

    # Request more than actual DB stock, but less than Redis cache
    requested_qty = actual_db_stock + 2
    item_quantities = {pid: requested_qty}

    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            success, err, decrements = InventoryReservationService.reserve_inventory(
                cursor=cursor,
                conn=conn,
                item_quantities=item_quantities
            )
            assert success is False
            assert "Insufficient stock" in err

    # Redis must have rolled back the decrement
    assert RedisService.get_stock(pid) == stale_high_redis_stock


def test_active_reconciliation_syncs_cache_to_authoritative_database(app_client):
    """
    Verify InventoryReservationService.reconcile_stock_with_database actively
    detects drifted Redis keys and synchronizes them to match PostgreSQL records.
    """
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT product_id, stock FROM products LIMIT 3")
            rows = cursor.fetchall()
            pids = [r['product_id'] if isinstance(r, dict) else r[0] for r in rows]
            actual_stocks = {
                (r['product_id'] if isinstance(r, dict) else r[0]): (r['stock'] if isinstance(r, dict) else r[1])
                for r in rows
            }

    # Simulate cache drift on first product
    target_pid = pids[0]
    drifted_val = actual_stocks[target_pid] + 99
    RedisService.set_stock(target_pid, drifted_val)
    assert RedisService.get_stock(target_pid) == drifted_val

    # Run active reconciliation
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            report = InventoryReservationService.reconcile_stock_with_database(cursor, product_ids=[target_pid])

    assert report['checked'] == 1
    assert report['synced'] == 1
    assert report['discrepancies'][0]['product_id'] == target_pid
    assert report['discrepancies'][0]['redis_stock'] == drifted_val
    assert report['discrepancies'][0]['authoritative_db_stock'] == actual_stocks[target_pid]

    # Verify Redis is now re-synchronized with PostgreSQL source of truth
    assert RedisService.get_stock(target_pid) == actual_stocks[target_pid]
