"""
Order Data Repository.
Handles admin order lookups, order status lifecycle transitions,
order line items queries, and pending orders staging.
"""
import json
import logging
from typing import Any, Dict, List, Optional
from psycopg2.extras import RealDictCursor
from database import get_db_connection, DatabaseError

logger = logging.getLogger("dailydrop.repositories.order")


def get_all_orders_with_user_info() -> List[Dict[str, Any]]:
    """Retrieve all orders joined with customer details for Admin Dashboard."""
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute('''
                    SELECT o.*, COALESCE(u.email, 'customer@dailydrop.com') as user_email
                    FROM orders o
                    LEFT JOIN users u ON o.user_id = u.id
                    ORDER BY o.order_date DESC
                ''')
                return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"Error retrieving all orders for admin: {e}")
        raise DatabaseError(f"Failed to retrieve orders: {e}") from e


def update_order_status(order_id: int, status: str) -> bool:
    """Update order delivery status."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute('UPDATE orders SET status = %s WHERE order_id = %s', (status, order_id))
                return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Error updating order status: {e}")
        raise DatabaseError(f"Failed to update order status: {e}") from e


def get_order_items(order_id: int) -> List[Dict[str, Any]]:
    """Retrieve normalized relational line items for a specific order."""
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute('''
                    SELECT id, order_id, product_id, product_name, price, quantity, image_path, subtotal
                    FROM order_items
                    WHERE order_id = %s
                    ORDER BY id ASC
                ''', (order_id,))
                rows = cursor.fetchall()
                results = []
                for r in rows:
                    item_d = dict(r)
                    item_d['price'] = float(item_d['price'])
                    item_d['subtotal'] = float(item_d['subtotal'])
                    item_d['image'] = item_d.get('image_path') or '/static/logo1.webp'
                    item_d['name'] = item_d.get('product_name')
                    results.append(item_d)
                return results
    except Exception as e:
        logger.error(f"Error fetching order items for order #{order_id}: {e}")
        return []


def save_pending_order(razorpay_order_id: str, user_id: Optional[int], full_name: str,
                       phone_number: str, address: str, products: Any, total_amount: float,
                       city: Optional[str] = 'Bangalore') -> bool:
    """Save pending order details to handle client disconnects during payment."""
    try:
        products_json = json.dumps(products) if not isinstance(products, str) else products
        target_city = city or 'Bangalore'
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                # Validate user_id exists if provided to prevent foreign key aborts on live DB
                validated_user_id = user_id
                if user_id is not None:
                    try:
                        cursor.execute("SELECT id FROM users WHERE id = %s", (user_id,))
                        if not cursor.fetchone():
                            logger.warning(f"User ID #{user_id} not found in users table. Setting pending_order user_id to None.")
                            validated_user_id = None
                    except Exception:
                        pass

                try:
                    cursor.execute("SAVEPOINT save_pending_sp")
                    try:
                        cursor.execute('''
                            INSERT INTO pending_orders (razorpay_order_id, user_id, full_name, phone_number, address, city, products_data, total_amount)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (razorpay_order_id) DO UPDATE SET
                                user_id = EXCLUDED.user_id,
                                full_name = EXCLUDED.full_name,
                                phone_number = EXCLUDED.phone_number,
                                address = EXCLUDED.address,
                                city = EXCLUDED.city,
                                products_data = EXCLUDED.products_data,
                                total_amount = EXCLUDED.total_amount
                        ''', (razorpay_order_id, validated_user_id, full_name, phone_number, address, target_city, products_json, total_amount))
                    except Exception:
                        cursor.execute('''
                            INSERT INTO pending_orders (razorpay_order_id, user_id, full_name, phone_number, address, products_data, total_amount)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (razorpay_order_id) DO UPDATE SET
                                user_id = EXCLUDED.user_id,
                                full_name = EXCLUDED.full_name,
                                phone_number = EXCLUDED.phone_number,
                                address = EXCLUDED.address,
                                products_data = EXCLUDED.products_data,
                                total_amount = EXCLUDED.total_amount
                        ''', (razorpay_order_id, validated_user_id, full_name, phone_number, address, products_json, total_amount))
                    cursor.execute("RELEASE SAVEPOINT save_pending_sp")
                except Exception:
                    try:
                        cursor.execute("ROLLBACK TO SAVEPOINT save_pending_sp")
                    except Exception:
                        pass
                    # Fallback for environments or SQLite without ON CONFLICT DO UPDATE
                    cursor.execute('DELETE FROM pending_orders WHERE razorpay_order_id = %s', (razorpay_order_id,))
                    try:
                        cursor.execute('''
                            INSERT INTO pending_orders (razorpay_order_id, user_id, full_name, phone_number, address, city, products_data, total_amount)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ''', (razorpay_order_id, validated_user_id, full_name, phone_number, address, target_city, products_json, total_amount))
                    except Exception:
                        cursor.execute('''
                            INSERT INTO pending_orders (razorpay_order_id, user_id, full_name, phone_number, address, products_data, total_amount)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ''', (razorpay_order_id, validated_user_id, full_name, phone_number, address, products_json, total_amount))
                return True
    except Exception as e:
        logger.error(f"Error saving pending order for {razorpay_order_id}: {e}")
        return False


def get_pending_order(razorpay_order_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve pending order by Razorpay order ID."""
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute('SELECT * FROM pending_orders WHERE razorpay_order_id = %s', (razorpay_order_id,))
                row = cursor.fetchone()
                return dict(row) if row else None
    except Exception as e:
        logger.error(f"Error getting pending order {razorpay_order_id}: {e}")
        return None


def delete_pending_order(razorpay_order_id: str) -> bool:
    """Delete a fulfilled or cancelled pending order."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute('DELETE FROM pending_orders WHERE razorpay_order_id = %s', (razorpay_order_id,))
                return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Error deleting pending order {razorpay_order_id}: {e}")
        return False
