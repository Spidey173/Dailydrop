"""
Order persistence service.
Handles database persistence of orders and normalized relational order_items.
"""
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class OrderPersistenceService:
    """Handles ACID database persistence for orders and line items."""

    @classmethod
    def persist_order(
        cls,
        cursor: Any,
        conn: Any,
        user_id: int,
        full_name: str,
        phone_number: str,
        address: str,
        products_json: str,
        authoritative_total: float,
        status: str,
        payment_method: str = 'COD',
        payment_id: Optional[str] = None,
        city: Optional[str] = 'Bangalore',
        delivery_duration_minutes: Optional[float] = 7.5
    ) -> int:
        """
        Inserts the master order record, supporting extended schema with graceful fallback.
        Returns:
            order_id (int)
        """
        target_city = city or 'Bangalore'
        duration = float(delivery_duration_minutes) if delivery_duration_minutes else 7.5

        insert_variants = [
            (
                """
                INSERT INTO orders (user_id, full_name, phone_number, address, city, delivery_duration_minutes, products_ordered, total_amount, status, payment_method, payment_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING order_id
                """,
                (user_id, full_name, phone_number, address, target_city, duration, products_json, authoritative_total, status, payment_method, payment_id)
            ),
            (
                """
                INSERT INTO orders (user_id, full_name, phone_number, address, city, products_ordered, total_amount, status, payment_method, payment_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING order_id
                """,
                (user_id, full_name, phone_number, address, target_city, products_json, authoritative_total, status, payment_method, payment_id)
            ),
            (
                """
                INSERT INTO orders (user_id, full_name, phone_number, address, products_ordered, total_amount, status, payment_method, payment_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING order_id
                """,
                (user_id, full_name, phone_number, address, products_json, authoritative_total, status, payment_method, payment_id)
            ),
            (
                """
                INSERT INTO orders (user_id, full_name, phone_number, address, products_ordered, total_amount, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING order_id
                """,
                (user_id, full_name, phone_number, address, products_json, authoritative_total, status)
            ),
        ]

        order_id = None
        for i, (query, params) in enumerate(insert_variants):
            sp_name = f"order_insert_sp_{i}"
            cursor.execute(f"SAVEPOINT {sp_name}")
            try:
                cursor.execute(query, params)
                order_row = cursor.fetchone()
                order_id = order_row['order_id'] if isinstance(order_row, dict) else order_row[0]
                cursor.execute(f"RELEASE SAVEPOINT {sp_name}")
                break
            except Exception:
                cursor.execute(f"ROLLBACK TO SAVEPOINT {sp_name}")
                if i == len(insert_variants) - 1:
                    raise

        return order_id

    @classmethod
    def persist_order_items(
        cls,
        cursor: Any,
        order_id: int,
        resolved_items: List[Dict[str, Any]]
    ) -> None:
        """Inserts normalized relational rows into order_items table."""
        for r_item in resolved_items:
            cursor.execute(
                """
                INSERT INTO order_items (order_id, product_id, product_name, price, quantity, image_path, subtotal)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    order_id,
                    r_item['product_id'],
                    r_item['name'],
                    r_item['price'],
                    r_item['quantity'],
                    r_item['image'],
                    r_item['subtotal']
                )
            )
