"""
PostgreSQL Concurrency & Race Protection Integration Tests.
Proves that under real database transaction isolation, two concurrent checkouts
for the last unit of stock result in exactly one success and zero overselling.
"""
import threading
import pytest
from app import create_app
from database import get_db_connection
from repositories.product_repository import add_product, get_product_by_id, delete_product
from services.order_service import OrderService


@pytest.mark.postgres
def test_postgres_concurrent_checkout_last_unit_stock():
    """
    Prove that two concurrent checkouts racing for the last unit of stock
    result in exactly ONE success and ONE failure with zero negative stock.
    """
    app = create_app('testing')
    with app.app_context():
        # 1. Provision product with exactly 1 unit of stock
        prod_id = add_product(
            name="Exclusive Limited Drop Item",
            price=199.00,
            category="Grocery",
            stock=1
        )
        assert prod_id is not None

        results = []
        barrier = threading.Barrier(2)

        def attempt_checkout(thread_id: int):
            cart = [{"product_id": prod_id, "name": "Exclusive Limited Drop Item", "price": 199.00, "quantity": 1}]
            # Synchronize threads so they hit OrderService.create_order simultaneously
            try:
                barrier.wait(timeout=5)
            except Exception:
                pass

            s, m, o = OrderService.create_order(
                user_id=1,
                full_name=f"Concurrent Racer {thread_id}",
                phone_number="9876543210",
                address="123 Finish Line Blvd",
                products=cart,
                total_amount=229.00,
                payment_method="COD",
                city="Bangalore"
            )
            results.append((s, m, o))

        t1 = threading.Thread(target=attempt_checkout, args=(1,))
        t2 = threading.Thread(target=attempt_checkout, args=(2,))

        t1.start()
        t2.start()
        t1.join()
        t2.join()

        successes = [r for r in results if r[0] is True]
        failures = [r for r in results if r[0] is False]

        assert len(successes) == 1, f"Expected exactly 1 checkout success, got {len(successes)}"
        assert len(failures) == 1, f"Expected exactly 1 checkout failure, got {len(failures)}"
        assert "Insufficient stock" in failures[0][1]

        # Verify database stock in PostgreSQL is exactly 0 and never negative
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT stock FROM products WHERE product_id = %s", (prod_id,))
                row = cursor.fetchone()
                final_stock = row['stock'] if isinstance(row, dict) else row[0]
                assert final_stock == 0, f"Stock must be exactly 0, found {final_stock}"
