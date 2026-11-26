"""
Tests verifying elimination of N+1 database queries during cart validation and inventory reservation.
"""
import pytest
from app import create_app
from core.database import get_db_connection
from services.catalog_validation_service import CatalogValidationService
from services.inventory_reservation_service import InventoryReservationService


@pytest.fixture
def test_app():
    app = create_app('testing')
    with app.app_context():
        yield app


def test_catalog_validation_batches_product_lookup(test_app):
    """
    Verify that CatalogValidationService batches product lookups into a single
    query using product_id = ANY(%s) instead of N individual queries.
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT product_id, name, price, stock FROM products LIMIT 3")
            rows = cur.fetchall()
            pids = [r['product_id'] if isinstance(r, dict) else r[0] for r in rows]

    cart = [{"product_id": pid, "quantity": 1} for pid in pids]

    select_queries = []

    class QueryCountingCursor:
        def __init__(self, real_cursor):
            self._real = real_cursor

        def execute(self, sql, params=None):
            if "SELECT" in sql.upper() and "FROM PRODUCTS" in sql.upper():
                select_queries.append(sql)
            return self._real.execute(sql, params)

        def fetchone(self):
            return self._real.fetchone()

        def fetchall(self):
            return self._real.fetchall()

    with get_db_connection() as conn:
        with conn.cursor() as raw_cur:
            proxy_cur = QueryCountingCursor(raw_cur)
            valid, err, resolved, item_qtys, total = CatalogValidationService.validate_and_resolve_cart(
                proxy_cur, cart
            )

    assert valid is True
    assert len(resolved) == 3
    # Must execute exactly 1 batched SELECT query using product_id = ANY(%s), not 3 separate queries!
    assert len(select_queries) == 1, f"Expected 1 batched query, got {len(select_queries)} queries: {select_queries}"
    assert "ANY" in select_queries[0] or "IN" in select_queries[0]


def test_inventory_reservation_avoids_requerying_stock(test_app):
    """
    Verify that InventoryReservationService uses pre-fetched stock and does not
    issue redundant SELECT queries for products during reservation.
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT product_id, name, price, stock FROM products LIMIT 3")
            rows = cur.fetchall()
            pids = [r['product_id'] if isinstance(r, dict) else r[0] for r in rows]
            stocks = {
                (r['product_id'] if isinstance(r, dict) else r[0]): (r['stock'] if isinstance(r, dict) else r[3])
                for r in rows
            }
            names = {
                (r['product_id'] if isinstance(r, dict) else r[0]): (r['name'] if isinstance(r, dict) else r[1])
                for r in rows
            }

    item_quantities = {pid: 1 for pid in pids}
    select_queries = []

    class QueryCountingCursor:
        def __init__(self, real_cursor):
            self._real = real_cursor

        def execute(self, sql, params=None):
            if "SELECT" in sql.upper() and "FROM PRODUCTS" in sql.upper():
                select_queries.append(sql)
            return self._real.execute(sql, params)

        def fetchone(self):
            return self._real.fetchone()

        def fetchall(self):
            return self._real.fetchall()

        @property
        def rowcount(self):
            return self._real.rowcount

    with get_db_connection() as conn:
        with conn.cursor() as raw_cur:
            proxy_cur = QueryCountingCursor(raw_cur)
            ok, err, decs = InventoryReservationService.reserve_inventory(
                cursor=proxy_cur,
                conn=conn,
                item_quantities=item_quantities,
                item_stocks=stocks,
                item_names=names
            )

    assert ok is True
    # When item_stocks is passed, no redundant SELECT queries should be executed
    assert len(select_queries) == 0, f"Expected 0 redundant SELECT queries, got {len(select_queries)}: {select_queries}"
