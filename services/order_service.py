"""
Order service managing checkout, order history retrieval, status updates, and analytics.
"""
from typing import Optional, List, Dict, Any, Tuple
import json
import time
import logging
from datetime import datetime
from database import (
    get_db_connection, DatabaseError, get_all_orders_with_user_info,
    update_order_status as db_update_order_status, get_dashboard_stats,
    get_sales_data, get_category_revenue, get_hourly_order_distribution,
    clear_analytics_cache, get_unified_analytics
)
from utils import validate_order_data, sanitize_string

logger = logging.getLogger(__name__)

_ANALYTICS_CACHE: Dict[str, Tuple[float, Dict[str, Any]]] = {}
_ANALYTICS_TTL = 60.0  # 60 seconds in-memory cache for ultra-fast admin dashboard


class OrderService:
    """Service providing order placement, history tracking, and sales analytics."""


    @staticmethod
    def create_order(user_id: int, full_name: str, phone_number: str, address: str,
                     products: Any, total_amount: float,
                     payment_method: str = 'COD',
                     payment_id: Optional[str] = None,
                     status: str = 'Processing') -> Tuple[bool, str, Optional[int]]:
        """
        Validate and save a customer order.

        Returns:
            Tuple of (success, message, order_id).
        """
        full_name = sanitize_string(full_name)
        address = sanitize_string(address)

        is_valid, error_msg = validate_order_data(full_name, phone_number, address, products)
        if not is_valid:
            return False, error_msg, None

        try:
            total_amount = float(total_amount)
            if total_amount <= 0:
                return False, 'Invalid total amount', None
        except (ValueError, TypeError):
            return False, 'Invalid total amount format', None

        # Parse products list
        try:
            items_list = json.loads(products) if isinstance(products, str) else list(products)
        except Exception:
            return False, 'Invalid products format', None

        if not items_list:
            return False, 'Cart cannot be empty', None

        products_json = json.dumps(items_list)
        from collections import defaultdict
        from database import clear_product_cache

        try:
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    # 1. Inspect cart items and strictly resolve against real catalog products
                    resolved_items = []
                    item_quantities = defaultdict(int)

                    for item in items_list:
                        if not isinstance(item, dict):
                            return False, 'Invalid cart item structure', None
                        qty = int(item.get('quantity', 1))
                        if qty <= 0:
                            return False, 'Product quantity must be at least 1', None

                        name = item.get('name', '')
                        img = item.get('image') or item.get('image_path') or '/static/logo1.webp'
                        pid = item.get('product_id') or item.get('id')

                        prod_row = None
                        if pid is not None:
                            try:
                                cursor.execute("SELECT product_id, name, stock, price, image_path FROM products WHERE product_id = %s", (int(pid),))
                                prod_row = cursor.fetchone()
                            except (ValueError, TypeError):
                                prod_row = None
                            except Exception as db_err:
                                conn.rollback()
                                logger.error(f"Database error during product lookup #{pid}: {db_err}")
                                return False, 'Database error during catalog lookup', None

                        if not prod_row and name:
                            try:
                                cursor.execute("SELECT product_id, name, stock, price, image_path FROM products WHERE LOWER(name) = LOWER(%s)", (name.strip(),))
                                prod_row = cursor.fetchone()
                            except Exception as db_err:
                                conn.rollback()
                                logger.error(f"Database error during product name lookup '{name}': {db_err}")
                                return False, 'Database error during catalog lookup', None

                        if not prod_row and name:
                            try:
                                cursor.execute("SELECT product_id, name, stock, price, image_path FROM products WHERE name ILIKE %s ORDER BY LENGTH(name) ASC LIMIT 1", (f"%{name.strip()}%",))
                                prod_row = cursor.fetchone()
                            except Exception as db_err:
                                conn.rollback()
                                logger.error(f"Database error during product pattern lookup '{name}': {db_err}")
                                return False, 'Database error during catalog lookup', None

                        if not prod_row:
                            conn.rollback()
                            identifier = name or (f"ID #{pid}" if pid else "item")
                            logger.warning(f"Rejected checkout: Product '{identifier}' not found in catalog database.")
                            return False, f"Product '{identifier}' not found in catalog", None

                        r_pid = prod_row['product_id'] if isinstance(prod_row, dict) else prod_row[0]
                        r_name = prod_row['name'] if isinstance(prod_row, dict) else prod_row[1]
                        raw_price = prod_row.get('price') if isinstance(prod_row, dict) else prod_row[3]

                        # Strictly enforce authoritative catalog price; reject if missing or corrupt in database
                        if raw_price is None or float(raw_price) <= 0:
                            conn.rollback()
                            logger.error(f"Missing authoritative price in database for catalog item #{r_pid} ('{r_name}')")
                            return False, f"Pricing error for product '{r_name}'. Order cannot proceed.", None

                        r_price = float(raw_price)
                        r_img = (prod_row['image_path'] if isinstance(prod_row, dict) else prod_row[4]) or img

                        subtotal = round(r_price * qty, 2)
                        item_quantities[r_pid] += qty
                        resolved_items.append({
                            'product_id': r_pid,
                            'name': r_name,
                            'price': r_price,
                            'quantity': qty,
                            'image': r_img,
                            'subtotal': subtotal
                        })

                    # Recalculate authoritative order totals from database
                    computed_subtotal = round(sum(i['subtotal'] for i in resolved_items), 2)
                    computed_fee = 0.0 if computed_subtotal >= 500.0 else 30.0
                    authoritative_total = round(computed_subtotal + computed_fee, 2)
                    products_json = json.dumps(resolved_items)

                    # 2. Flash-Sale Concurrency Protection: Distributed Redis Lua Script (< 1ms)
                    # Atomically check & decrement in Redis memory before executing heavy DB row writes.
                    from services.redis_service import RedisService
                    redis_decrements = {}
                    for r_pid, required_qty in item_quantities.items():
                        cursor.execute("SELECT name, stock FROM products WHERE product_id = %s", (r_pid,))
                        p_info = cursor.fetchone()
                        avail_stock = (p_info['stock'] if isinstance(p_info, dict) else p_info[1]) if p_info else None
                        p_name = (p_info['name'] if isinstance(p_info, dict) else p_info[0]) if p_info else f"Product #{r_pid}"

                        success, msg, rem = RedisService.atomic_decrement_stock(
                            product_id=r_pid,
                            quantity=required_qty,
                            fallback_db_stock=avail_stock
                        )
                        if not success:
                            # Fast fail in < 1ms: rollback any prior items decremented in Redis
                            for rolled_pid, rolled_qty in redis_decrements.items():
                                RedisService.atomic_rollback_stock(rolled_pid, rolled_qty)
                            logger.warning(f"[Flash-Sale Fast Reject] Insufficient stock in Redis for '{p_name}' (available {rem}, requested {required_qty})")
                            return False, f"Insufficient stock for '{p_name}'. Only {rem} units left in stock.", None
                        redis_decrements[r_pid] = required_qty

                    # 3. Relational PostgreSQL Inventory Update:
                    # UPDATE products SET stock = stock - %s WHERE product_id = %s AND stock >= %s
                    # Persists state to ACID relational database
                    for r_pid, required_qty in item_quantities.items():
                        cursor.execute(
                            "UPDATE products SET stock = stock - %s WHERE product_id = %s AND stock >= %s",
                            (required_qty, r_pid, required_qty)
                        )
                        if cursor.rowcount == 0:
                            # Overselling prevented in DB - rollback transaction & Redis decrements
                            cursor.execute("SELECT name, stock FROM products WHERE product_id = %s", (r_pid,))
                            p_info = cursor.fetchone()
                            p_name = (p_info['name'] if isinstance(p_info, dict) else p_info[0]) if p_info else f"Product #{r_pid}"
                            avail_stock = (p_info['stock'] if isinstance(p_info, dict) else p_info[1]) if p_info else 0
                            conn.rollback()
                            for rolled_pid, rolled_qty in redis_decrements.items():
                                RedisService.atomic_rollback_stock(rolled_pid, rolled_qty)
                            logger.warning(f"Overselling prevented: Insufficient stock for '{p_name}' (requested {required_qty}, available {avail_stock})")
                            return False, f"Insufficient stock for '{p_name}'. Only {avail_stock} units left in stock.", None

                    # 4. Insert order record using authoritative total and resolved products
                    try:
                        cursor.execute('''
                            INSERT INTO orders (user_id, full_name, phone_number, address, products_ordered, total_amount, status, payment_method, payment_id)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                            RETURNING order_id
                        ''', (user_id, full_name, phone_number, address, products_json, authoritative_total, status, payment_method, payment_id))
                    except Exception:
                        conn.rollback()
                        cursor.execute('''
                            INSERT INTO orders (user_id, full_name, phone_number, address, products_ordered, total_amount, status)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                            RETURNING order_id
                        ''', (user_id, full_name, phone_number, address, products_json, authoritative_total, status))

                    order_row = cursor.fetchone()
                    order_id = order_row['order_id'] if isinstance(order_row, dict) else order_row[0]

                    # 5. Insert normalized relational rows into order_items
                    for r_item in resolved_items:
                        cursor.execute('''
                            INSERT INTO order_items (order_id, product_id, product_name, price, quantity, image_path, subtotal)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)

                        ''', (
                            order_id,
                            r_item['product_id'],
                            r_item['name'],
                            r_item['price'],
                            r_item['quantity'],
                            r_item['image'],
                            r_item['subtotal']
                        ))

                    # 6. Transactional Outbox Pattern: Record ORDER_CREATED event in SAME atomic transaction
                    try:
                        from services.outbox_service import OutboxService
                        outbox_payload = {
                            'order_id': order_id,
                            'user_id': user_id,
                            'full_name': full_name,
                            'phone_number': phone_number,
                            'total_amount': total_amount,
                            'payment_method': payment_method,
                            'payment_id': payment_id,
                            'status': status,
                            'products': resolved_items
                        }
                        OutboxService.record_event(
                            cursor=cursor,
                            event_type='ORDER_CREATED',
                            aggregate_type='order',
                            aggregate_id=order_id,
                            payload=outbox_payload
                        )
                    except Exception as outbox_err:
                        logger.warning(f"Could not record outbox event: {outbox_err}")

            clear_product_cache()
            clear_analytics_cache()
            _ANALYTICS_CACHE.clear()

            # 7. Asynchronous Worker Queue: Relay events to background Celery/RQ workers
            try:
                from services.outbox_service import OutboxService
                OutboxService.relay_events(limit=10)
            except Exception as relay_err:
                logger.warning(f"Could not immediately relay outbox events: {relay_err}")

            logger.info(f"Order #{order_id} ({payment_method}) placed successfully with {len(resolved_items)} normalized items by user #{user_id}")
            return True, 'Order placed successfully', order_id
        except DatabaseError as e:
            for rolled_pid, rolled_qty in redis_decrements.items():
                try:
                    from services.redis_service import RedisService
                    RedisService.atomic_rollback_stock(rolled_pid, rolled_qty)
                except Exception:
                    pass
            logger.error(f"Error saving order: {e}")
            return False, 'Failed to save order to database', None

    @staticmethod
    def get_user_orders(user_id: int) -> List[Dict[str, Any]]:
        """Retrieve order history for a customer with normalized order_items and sequential numbering."""
        from psycopg2.extras import RealDictCursor
        try:
            with get_db_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    try:
                        cursor.execute(
                            '''
                            SELECT *,
                                   ROW_NUMBER() OVER (ORDER BY order_date ASC, order_id ASC) AS user_order_number
                            FROM orders
                            WHERE user_id = %s
                            ORDER BY order_date DESC, order_id DESC
                            ''',
                            (user_id,)
                        )
                        order_rows = cursor.fetchall()
                    except Exception:
                        conn.rollback()
                        cursor.execute(
                            'SELECT * FROM orders WHERE user_id = %s ORDER BY order_date DESC, order_id DESC',
                            (user_id,)
                        )
                        order_rows = cursor.fetchall()

            order_ids = [dict(o)['order_id'] for o in order_rows]
            items_by_order: Dict[int, List[Dict[str, Any]]] = {}
            if order_ids:
                try:
                    with get_db_connection() as conn:
                        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                            format_strings = ','.join(['%s'] * len(order_ids))
                            cursor.execute(f'''
                                SELECT id, order_id, product_id, product_name as name, price, quantity, image_path, subtotal
                                FROM order_items
                                WHERE order_id IN ({format_strings})
                                ORDER BY id ASC
                            ''', tuple(order_ids))
                            for row in cursor.fetchall():
                                item_d = dict(row)
                                img = item_d.get('image_path') or '/static/logo1.webp'
                                item_d['image'] = img
                                item_d['image_path'] = img
                                item_d['price'] = float(item_d['price'])
                                item_d['subtotal'] = float(item_d['subtotal'])
                                items_by_order.setdefault(item_d['order_id'], []).append(item_d)
                except Exception as e:
                    logger.warning(f"Could not load order_items for user orders: {e}")

            total_orders = len(order_rows)
            parsed_orders = []
            for idx, order in enumerate(order_rows):
                order_dict = dict(order)
                oid = order_dict['order_id']
                if order_dict.get('user_order_number') is None:
                    order_dict['user_order_number'] = total_orders - idx

                # Prioritize normalized relational items; fallback to JSON string if needed
                if oid in items_by_order and items_by_order[oid]:
                    order_dict['products'] = items_by_order[oid]
                else:
                    try:
                        order_dict['products'] = json.loads(order_dict['products_ordered'])
                    except Exception:
                        order_dict['products'] = []
                    for p in order_dict['products']:
                        if isinstance(p, dict):
                            img = p.get('image') or p.get('image_path') or '/static/logo1.webp'
                            p['image'] = img
                            p['image_path'] = img

                if isinstance(order_dict.get('order_date'), str):
                    try:
                        order_dict['order_date'] = datetime.fromisoformat(order_dict['order_date'])
                    except Exception:
                        pass
                parsed_orders.append(order_dict)

            return parsed_orders
        except DatabaseError as e:
            logger.error(f"Error fetching orders for user #{user_id}: {e}")
            return []

    @staticmethod
    def get_all_orders() -> List[Dict[str, Any]]:
        """Retrieve all orders with user info for admin dashboard."""
        try:
            return get_all_orders_with_user_info()
        except DatabaseError as e:
            logger.error(f"Error fetching all orders: {e}")
            return []

    VALID_ORDER_STATUSES = ['Paid', 'Processing', 'Packed', 'Shipped', 'Out for Delivery', 'Delivered', 'Cancelled']

    VALID_TRANSITIONS = {
        'Paid': {'Processing', 'Packed', 'Shipped', 'Out for Delivery', 'Delivered', 'Cancelled'},
        'Processing': {'Packed', 'Shipped', 'Out for Delivery', 'Delivered', 'Cancelled'},
        'Packed': {'Shipped', 'Out for Delivery', 'Delivered', 'Cancelled'},
        'Shipped': {'Out for Delivery', 'Delivered', 'Cancelled'},
        'Out for Delivery': {'Delivered', 'Cancelled'},
        'Delivered': set(),  # Terminal state: cannot change
        'Cancelled': set(),  # Terminal state: cannot change
    }


    @classmethod
    def update_status(cls, order_id: int, status: str, expected_current_status: Optional[str] = None) -> Tuple[bool, str]:
        """
        Atomically update status of an order within a single transaction with row-level locking.
        Guarantees strict state transitions and prevents race conditions under concurrent requests.
        """
        if status not in cls.VALID_ORDER_STATUSES:
            return False, f"Invalid status '{status}'. Must be one of: {', '.join(cls.VALID_ORDER_STATUSES)}"

        try:
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    # 1. Row-level exclusive lock within transaction (prevents concurrent race conditions)
                    cursor.execute("SELECT status FROM orders WHERE order_id = %s FOR UPDATE", (order_id,))
                    row = cursor.fetchone()
                    if not row:
                        return False, f"Order #{order_id} not found"
                    curr_status = row['status'] if isinstance(row, dict) else row[0]

                    # 2. Idempotent check
                    if curr_status == status:
                        return True, f"Order #{order_id} is already in {status} state"

                    # 3. Optimistic concurrency check (if expected status supplied)
                    if expected_current_status and curr_status != expected_current_status:
                        return False, f"Conflict: Order #{order_id} status changed to '{curr_status}' by another request."

                    # 4. Terminal state enforcement
                    if curr_status in ['Delivered', 'Cancelled']:
                        return False, f"Cannot change status of a {curr_status} order to {status}."

                    # 5. Valid transition enforcement
                    allowed_targets = cls.VALID_TRANSITIONS.get(curr_status, set())
                    if status not in allowed_targets:
                        return False, f"Invalid status transition from '{curr_status}' to '{status}'"

                    # 6. Atomic write in the SAME transaction before commit
                    cursor.execute("UPDATE orders SET status = %s WHERE order_id = %s", (status, order_id))
                    if cursor.rowcount == 0:
                        return False, f"Order #{order_id} not found"

            # Both read, lock, validation, and write committed together atomically upon exiting with block
            clear_analytics_cache()
            _ANALYTICS_CACHE.clear()
            return True, f"Order #{order_id} status updated to {status}"
        except DatabaseError as e:
            logger.error(f"Error updating status for order #{order_id}: {e}")
            return False, 'Failed to update order status'


    @staticmethod
    def get_analytics(days: int = 30) -> Dict[str, Any]:
        """Retrieve full administrative analytics with unified sub-millisecond responses."""
        try:
            return get_unified_analytics(days=days)
        except DatabaseError as e:
            logger.error(f"Error retrieving analytics: {e}")
            return {}

