"""
Order service managing checkout, order history retrieval, status updates, and analytics.
"""
from typing import Optional, List, Dict, Any, Tuple
import json
import logging
from datetime import datetime
from database import (
    get_db_connection, DatabaseError, get_all_orders_with_user_info,
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
                    # Guarantees true atomicity: if writing the outbox event fails, the entire transaction rolls back
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

    SCHEDULE_PROFILES = [
        # Distinct fulfillment curves tailored per order (all guaranteed strictly under 10 minutes)
        {"pack": 1.5, "transit": 4.0, "target": 7.0, "pack_text": "1.5 mins", "transit_text": "4 mins", "target_text": "7 mins"},
        {"pack": 2.0, "transit": 5.0, "target": 8.0, "pack_text": "2 mins", "transit_text": "5 mins", "target_text": "8 mins"},
        {"pack": 1.0, "transit": 3.5, "target": 6.0, "pack_text": "1 min", "transit_text": "3.5 mins", "target_text": "6 mins"},
        {"pack": 2.0, "transit": 5.5, "target": 9.0, "pack_text": "2 mins", "transit_text": "5.5 mins", "target_text": "9 mins"},
        {"pack": 1.0, "transit": 4.0, "target": 7.0, "pack_text": "1 min", "transit_text": "4 mins", "target_text": "7 mins"},
        {"pack": 1.5, "transit": 4.5, "target": 8.0, "pack_text": "1.5 mins", "transit_text": "4.5 mins", "target_text": "8 mins"},
    ]

    @classmethod
    def get_delivery_tracking(cls, order_date: Any, current_status: str = 'Processing', order_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Authoritative quick-commerce delivery tracker with varied realistic timings strictly under 10 minutes.
        Progression:
          Step 1: Order Placed   (0 -> pack_seconds)
          Step 2: Packing Items  (pack_seconds -> transit_seconds)
          Step 3: On the Way     (transit_seconds -> target_seconds)
          Step 4: Delivered      (target_seconds+ mins, guaranteed < 10 mins)
        """
        from datetime import timezone, timedelta

        # Select deterministic profile per order so repeated page views remain consistent and authentic
        if order_id is not None:
            try:
                profile_idx = abs(int(order_id)) % len(cls.SCHEDULE_PROFILES)
            except (ValueError, TypeError):
                profile_idx = 1
        else:
            profile_idx = 1  # Standard 8-min profile (< 10 mins)
        profile = cls.SCHEDULE_PROFILES[profile_idx]

        pack_seconds = profile['pack'] * 60.0
        transit_seconds = profile['transit'] * 60.0
        target_seconds = profile['target'] * 60.0
        target_mins_int = int(profile['target']) if profile['target'].is_integer() else profile['target']

        step1_time = "0 min"
        step2_time = profile['pack_text']
        step3_time = profile['transit_text']
        step4_time = profile['target_text']
        delivery_duration_text = f"Delivered in {profile['target_text']}"

        if not order_date:
            order_date = datetime.now(timezone.utc)
        elif isinstance(order_date, str):
            try:
                order_date = datetime.fromisoformat(order_date)
            except Exception:
                order_date = datetime.now(timezone.utc)

        # Standardize order_date and current time strictly to UTC
        if hasattr(order_date, 'tzinfo') and order_date.tzinfo:
            order_date_utc = order_date.astimezone(timezone.utc)
        else:
            order_date_utc = order_date.replace(tzinfo=timezone.utc)

        now_utc = datetime.now(timezone.utc)
        elapsed_seconds = max(0.0, (now_utc - order_date_utc).total_seconds())
        remaining_seconds = max(0.0, target_seconds - elapsed_seconds)

        step1_clock = order_date_utc.strftime('%I:%M %p')
        step2_clock = (order_date_utc + timedelta(minutes=profile['pack'])).strftime('%I:%M %p')
        step3_clock = (order_date_utc + timedelta(minutes=profile['transit'])).strftime('%I:%M %p')
        step4_clock = (order_date_utc + timedelta(minutes=profile['target'])).strftime('%I:%M %p')

        if current_status == 'Cancelled':
            return {
                'current_step': 0,
                'is_cancelled': True,
                'is_delivered': False,
                'effective_status': 'Cancelled',
                'badge_text': 'Cancelled',
                'badge_class': 'status-cancelled',
                'badge_icon': 'fas fa-ban',
                'status_message': 'This order was cancelled',
                'progress_percent': 0,
                'elapsed_seconds': int(elapsed_seconds),
                'remaining_seconds': 0,
                'eta_text': 'Cancelled',
                'order_date_iso': order_date.isoformat() if hasattr(order_date, 'isoformat') else str(order_date),
                'target_minutes': profile['target'],
                'target_seconds': int(target_seconds),
                'pack_seconds': int(pack_seconds),
                'transit_seconds': int(transit_seconds),
                'step1_time': step1_time,
                'step2_time': step2_time,
                'step3_time': step3_time,
                'step4_time': step4_time,
                'step1_clock': step1_clock,
                'step2_clock': step2_clock,
                'step3_clock': step3_clock,
                'step4_clock': step4_clock,
                'delivery_duration_text': delivery_duration_text,
            }

        # If manually marked Delivered or time elapsed >= target_seconds (strictly under 10 mins)
        if current_status == 'Delivered' or elapsed_seconds >= target_seconds:
            effective_status = 'Delivered'
            current_step = 4
            is_delivered = True
            progress_percent = 100
            badge_text = 'Delivered'
            badge_class = 'status-delivered'
            badge_icon = 'fas fa-circle-check'
            status_message = 'Delivered to your doorstep'
            eta_text = delivery_duration_text
        elif current_status in ('Out for Delivery', 'Shipped') or elapsed_seconds >= transit_seconds:
            # Stage 3: Out for Delivery (transit_seconds -> target_seconds)
            effective_status = 'Out for Delivery'
            current_step = 3
            is_delivered = False
            progress_percent = min(95, 60 + int(((elapsed_seconds - transit_seconds) / max(1.0, target_seconds - transit_seconds)) * 35))
            badge_text = 'Out for Delivery'
            badge_class = 'status-delivery'
            badge_icon = 'fas fa-motorcycle'
            rem_mins = max(1, int(round(remaining_seconds / 60.0)))
            status_message = 'Rider is on the way to your address'
            eta_text = f'Arriving in ~{rem_mins} min{"s" if rem_mins > 1 else ""}'
        elif current_status == 'Packed' or elapsed_seconds >= pack_seconds:
            # Stage 2: Packing (pack_seconds -> transit_seconds)
            effective_status = 'Packed'
            current_step = 2
            is_delivered = False
            progress_percent = min(58, 25 + int(((elapsed_seconds - pack_seconds) / max(1.0, transit_seconds - pack_seconds)) * 33))
            badge_text = 'Packing Order'
            badge_class = 'status-packing'
            badge_icon = 'fas fa-box-open'
            rem_mins = max(1, int(round(remaining_seconds / 60.0)))
            status_message = 'Items packed & quality checked at dark store'
            eta_text = f'Arriving in ~{rem_mins} mins'
        else:
            # Stage 1: Order Placed (0 -> pack_seconds)
            effective_status = current_status if current_status not in ('Processing', 'Created') else 'Order Placed'
            current_step = 1
            is_delivered = False
            progress_percent = min(22, 10 + int((elapsed_seconds / max(1.0, pack_seconds)) * 12))
            badge_text = 'Order Confirmed'
            badge_class = 'status-processing'
            badge_icon = 'fas fa-receipt'
            status_message = 'Order placed & confirmed with nearby hub'
            eta_text = f'{target_mins_int}-Min Fast Delivery'

        return {
            'current_step': current_step,
            'effective_status': effective_status,
            'is_cancelled': False,
            'is_delivered': is_delivered,
            'badge_text': badge_text,
            'badge_class': badge_class,
            'badge_icon': badge_icon,
            'status_message': status_message,
            'progress_percent': progress_percent,
            'elapsed_seconds': int(elapsed_seconds),
            'remaining_seconds': int(remaining_seconds),
            'eta_text': eta_text,
            'order_date_iso': order_date.isoformat() if hasattr(order_date, 'isoformat') else str(order_date),
            'target_minutes': profile['target'],
            'target_seconds': int(target_seconds),
            'pack_seconds': int(pack_seconds),
            'transit_seconds': int(transit_seconds),
            'step1_time': step1_time,
            'step2_time': step2_time,
            'step3_time': step3_time,
            'step4_time': step4_time,
            'step1_clock': step1_clock,
            'step2_clock': step2_clock,
            'step3_clock': step3_clock,
            'step4_clock': step4_clock,
            'delivery_duration_text': delivery_duration_text,
        }

    @staticmethod
    def get_order_by_id(order_id: int) -> Optional[Dict[str, Any]]:
        """Retrieve a single order by order_id."""
        from psycopg2.extras import RealDictCursor
        try:
            with get_db_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute("SELECT * FROM orders WHERE order_id = %s", (order_id,))
                    row = cursor.fetchone()
                    return dict(row) if row else None
        except DatabaseError as e:
            logger.error(f"Error fetching order #{order_id}: {e}")
            return None

    @classmethod
    def get_user_orders(cls, user_id: int) -> List[Dict[str, Any]]:
        """Retrieve order history for a customer with normalized order_items, sequential numbering, and live tracking."""
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

                # Enrich with varied quick-commerce under-10-minute delivery tracking stages
                tracking = cls.get_delivery_tracking(
                    order_dict.get('order_date'),
                    order_dict.get('status', 'Processing'),
                    order_id=oid
                )
                order_dict['tracking'] = tracking
                if tracking.get('is_delivered') and order_dict.get('status') not in ('Delivered', 'Cancelled'):
                    order_dict['status'] = 'Delivered'
                parsed_orders.append(order_dict)

            # Auto-promote orders older than 10 mins to 'Delivered' in DB if not already terminal
            delivered_ids = [
                parsed_orders[idx]['order_id']
                for idx, raw_order in enumerate(order_rows)
                if parsed_orders[idx].get('tracking', {}).get('is_delivered')
                and str(parsed_orders[idx].get('status')) == 'Delivered'
                and dict(raw_order).get('status') not in ('Delivered', 'Cancelled')
            ]
            if delivered_ids:
                try:
                    with get_db_connection() as conn:
                        with conn.cursor() as cursor:
                            format_strings = ','.join(['%s'] * len(delivered_ids))
                            cursor.execute(f'''
                                UPDATE orders
                                SET status = 'Delivered'
                                WHERE order_id IN ({format_strings})
                                  AND status NOT IN ('Delivered', 'Cancelled')
                            ''', tuple(delivered_ids))
                except Exception as ex:
                    logger.warning(f"Could not auto-promote orders to Delivered in DB: {ex}")

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

