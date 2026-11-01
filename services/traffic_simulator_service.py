"""
Autonomous Quick-Commerce Traffic & Order Simulator Service.
Maintains continuous realistic order volume, 10-minute SLA delivery metrics,
and revenue velocity across Neon PostgreSQL so analytics always remain vibrant.
"""

import json
import logging
import os
import random
import threading
import time
from datetime import datetime, timedelta, date
from typing import Any, Dict, List, Optional, Tuple

from database import get_db_connection, clear_analytics_cache
from services.order_persistence_service import OrderPersistenceService

logger = logging.getLogger(__name__)

# Realistic quick-commerce metro hubs & SLA performance baselines
METRO_HUBS = [
    {
        'city': 'Bangalore',
        'address_samples': [
            'Flat 402, Prestige Lakeside Habitat, Varthur, Bangalore - 560087',
            'Tower B, 804, Sobha Dream Acres, Panathur, Bangalore - 560103',
            'Apt 12B, Brigade Millennium, JP Nagar 7th Phase, Bangalore - 560078',
            'Villa 34, Adarsh Palm Retreat, Bellandur, Bangalore - 560103',
            '104, 3rd Cross, Indiranagar 100ft Road, Bangalore - 560038'
        ],
        'base_sla': 7.2
    },
    {
        'city': 'Delhi NCR',
        'address_samples': [
            'Tower 3, Apt 1104, Godrej Woods, Sector 43, Noida - 201303',
            'D-404, DLF Phase 5, Golf Course Road, Gurugram - 122002',
            'A-22, Hauz Khas Enclave, New Delhi - 110016',
            'Tower 7, 502, ATS One Hamlet, Sector 104, Noida - 201304',
            'Flat 601, Ambience Lagoon, NH-8, Gurugram - 122002'
        ],
        'base_sla': 7.8
    },
    {
        'city': 'Mumbai',
        'address_samples': [
            'Flat 1201, Lodha Park, Worli, Mumbai - 400013',
            'B-702, Hiranandani Gardens, Powai, Mumbai - 400076',
            'Apt 904, Rustomjee Elements, Upper Juhu, Mumbai - 400053',
            'Tower 2, 1403, Oberoi Woods, Goregaon East, Mumbai - 400063',
            '401, Sea Breeze Apartments, Bandra West, Mumbai - 400050'
        ],
        'base_sla': 8.1
    },
    {
        'city': 'Hyderabad',
        'address_samples': [
            'Villa 18, My Home Bhooja, HITEC City, Hyderabad - 500081',
            'Tower 4, Apt 802, Aparna Serene Park, Gachibowli, Hyderabad - 500032',
            'Flat 501, Jayabheri The Summit, Financial District, Hyderabad - 500075',
            'B-1102, Rainbow Vistas Rock Garden, Hitec City, Hyderabad - 500018',
            'Villa 9, Jubilee Hills Road No. 36, Hyderabad - 500033'
        ],
        'base_sla': 7.9
    },
    {
        'city': 'Pune',
        'address_samples': [
            'Flat 301, Amanora Park Town, Hadapsar, Pune - 411028',
            'Tower C, Apt 902, Blue Ridge, Hinjewadi Phase 1, Pune - 411057',
            'Apt 704, Marvel Arco, Magarpatta Road, Pune - 411028',
            'Villa 12, Panchshil Towers, Kharadi, Pune - 411014',
            '502, Rohan Mithila, Viman Nagar, Pune - 411014'
        ],
        'base_sla': 8.4
    }
]

# Fallback customers if database users table is empty
FALLBACK_CUSTOMERS = [
    {'name': 'Kavita Sharma', 'email': 'kavita.sharma623@gmail.com', 'phone': '+91 9845012345'},
    {'name': 'Prisha Singh', 'email': 'prisha.singh69@gmail.com', 'phone': '+91 9811234567'},
    {'name': 'Suresh Nair', 'email': 'suresh.nair141@gmail.com', 'phone': '+91 9820345678'},
    {'name': 'Arjun Mehta', 'email': 'arjun.mehta99@gmail.com', 'phone': '+91 9876543210'},
    {'name': 'Anita Deshmukh', 'email': 'anita.deshmukh67@gmail.com', 'phone': '+91 9890123456'},
    {'name': 'Sneha Agarwal', 'email': 'sneha.agarwal888@gmail.com', 'phone': '+91 9830123456'},
    {'name': 'Rohan Kulkarni', 'email': 'rohan.kulkarni45@gmail.com', 'phone': '+91 9860123456'},
    {'name': 'Pooja Iyer', 'email': 'pooja.iyer21@gmail.com', 'phone': '+91 9880123456'}
]


class TrafficSimulatorService:
    """Service to automatically simulate real-time quick-commerce orders."""

    _daemon_started: bool = False
    _daemon_lock: threading.Lock = threading.Lock()
    _last_activity_check: float = 0.0

    @classmethod
    def pulse(cls, count: int = 1, custom_datetime: Optional[datetime] = None, status: str = 'Delivered') -> List[Dict[str, Any]]:
        """
        Generates and saves one or more realistic quick-commerce orders into PostgreSQL.
        """
        results: List[Dict[str, Any]] = []

        try:
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    # 1. Fetch available customers
                    cursor.execute("SELECT id, name, email FROM users WHERE role != 'admin' LIMIT 50")
                    users_rows = cursor.fetchall()
                    customers = []
                    for u in users_rows:
                        uid = u['id'] if isinstance(u, dict) else u[0]
                        uname = u['name'] if isinstance(u, dict) else u[1]
                        uemail = u['email'] if isinstance(u, dict) else u[2]
                        customers.append({
                            'id': uid,
                            'name': uname or 'Quick Customer',
                            'email': uemail or 'customer@dailydrop.com',
                            'phone': f"+91 9{random.randint(100000000, 999999999)}"
                        })

                    if not customers:
                        customers = [{'id': 1, **c} for c in FALLBACK_CUSTOMERS]

                    # 2. Fetch active catalog products
                    cursor.execute("SELECT product_id, name, price, category, image_path, stock FROM products WHERE stock > 0 LIMIT 150")
                    prod_rows = cursor.fetchall()
                    products = []
                    for p in prod_rows:
                        products.append({
                            'product_id': p['product_id'] if isinstance(p, dict) else p[0],
                            'name': p['name'] if isinstance(p, dict) else p[1],
                            'price': float(p['price'] if isinstance(p, dict) else p[2]),
                            'category': p['category'] if isinstance(p, dict) else p[3],
                            'image': (p['image_path'] if isinstance(p, dict) else p[4]) or '/static/product-placeholder.svg',
                            'stock': int(p['stock'] if isinstance(p, dict) else p[5])
                        })

                    if not products:
                        logger.warning("Traffic simulator: No catalog products available.")
                        return []

                    for _ in range(count):
                        customer = random.choice(customers)
                        hub = random.choice(METRO_HUBS)
                        city = hub['city']
                        address = random.choice(hub['address_samples'])
                        order_time = custom_datetime or datetime.now()

                        # Select 1 to 4 items for quick-commerce basket
                        num_items = random.choices([1, 2, 3, 4], weights=[0.25, 0.45, 0.20, 0.10])[0]
                        chosen_prods = random.sample(products, min(num_items, len(products)))

                        resolved_items = []
                        subtotal = 0.0

                        for p in chosen_prods:
                            qty = random.choices([1, 2, 3], weights=[0.75, 0.20, 0.05])[0]
                            item_price = p['price']
                            item_subtotal = round(item_price * qty, 2)
                            subtotal += item_subtotal
                            resolved_items.append({
                                'product_id': p['product_id'],
                                'name': p['name'],
                                'price': item_price,
                                'quantity': qty,
                                'subtotal': item_subtotal,
                                'image': p['image']
                            })

                        # Free delivery over ₹399, else ₹30 delivery fee
                        delivery_fee = 0.0 if subtotal >= 399.0 else 30.0
                        total_amount = round(subtotal + delivery_fee, 2)

                        # Payment method: 70% Razorpay, 30% COD
                        is_razorpay = random.random() < 0.70
                        payment_method = 'Razorpay' if is_razorpay else 'COD'
                        payment_id = f"pay_live_{random.randint(100000, 999999)}" if is_razorpay else None

                        # Quick-commerce delivery speed (strictly under 10 minutes)
                        duration = round(hub['base_sla'] + random.uniform(-0.6, 0.6), 1)

                        # Persist order record
                        products_json = json.dumps(resolved_items)
                        cursor.execute(
                            """
                            INSERT INTO orders (user_id, full_name, phone_number, address, city,
                                                delivery_duration_minutes, products_ordered, total_amount,
                                                status, payment_method, payment_id, order_date)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            RETURNING order_id
                            """,
                            (
                                customer['id'],
                                customer['name'],
                                customer['phone'],
                                address,
                                city,
                                duration,
                                products_json,
                                total_amount,
                                status,
                                payment_method,
                                payment_id,
                                order_time
                            )
                        )
                        order_row = cursor.fetchone()
                        order_id = order_row['order_id'] if isinstance(order_row, dict) else order_row[0]

                        # Persist line items
                        OrderPersistenceService.persist_order_items(cursor, order_id, resolved_items)

                        # Gently replenish stock if low so catalog never runs dry
                        for p in chosen_prods:
                            cursor.execute(
                                "UPDATE products SET stock = stock + 30 WHERE product_id = %s AND stock < 10",
                                (p['product_id'],)
                            )

                        conn.commit()

                        results.append({
                            'order_id': order_id,
                            'customer': customer['name'],
                            'city': city,
                            'total_amount': total_amount,
                            'items_count': len(resolved_items),
                            'duration': duration,
                            'status': status,
                            'order_date': order_time.strftime('%Y-%m-%d %H:%M:%S')
                        })

                    # Flush analytics cache so updates reflect instantly in dashboard
                    clear_analytics_cache()

        except Exception as e:
            logger.error(f"Traffic simulator pulse failed: {e}")

        return results

    @classmethod
    def ensure_daily_activity(cls, max_catchup_days: int = 30) -> int:
        """
        Detects if recent days or today have missing orders, and backfills
        realistic quick-commerce transactions so daily GMV curves never flatline.
        Returns total number of synthetic orders created.
        """
        now = datetime.now()
        today = now.date()
        total_created = 0

        try:
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT MAX(order_date) as latest_date FROM orders")
                    row = cursor.fetchone()
                    latest_raw = row['latest_date'] if isinstance(row, dict) else (row[0] if row else None)

            if not latest_raw:
                return 0

            if isinstance(latest_raw, str):
                try:
                    latest_dt = datetime.fromisoformat(latest_raw.replace('Z', '+00:00'))
                except Exception:
                    latest_dt = datetime.strptime(latest_raw[:19], '%Y-%m-%d %H:%M:%S')
            else:
                latest_dt = latest_raw

            latest_date = latest_dt.date()

            # 1. Backfill any missed calendar days between latest_date and today
            if latest_date < today:
                days_gap = (today - latest_date).days
                catchup_days = min(days_gap, max_catchup_days)

                for day_offset in range(1, catchup_days):
                    target_date = latest_date + timedelta(days=day_offset)
                    # 6 to 10 realistic orders for missed day
                    day_orders_count = random.randint(6, 10)
                    for _ in range(day_orders_count):
                        # Distribute realistically: morning rush, lunch, evening dinner peak
                        rush_window = random.choices(['morning', 'afternoon', 'evening'], weights=[0.35, 0.20, 0.45])[0]
                        if rush_window == 'morning':
                            hour = random.randint(8, 10)
                            minute = random.randint(0, 59)
                        elif rush_window == 'afternoon':
                            hour = random.randint(12, 15)
                            minute = random.randint(0, 59)
                        else:
                            hour = random.randint(18, 21)
                            minute = random.randint(0, 59)

                        order_dt = datetime(target_date.year, target_date.month, target_date.day, hour, minute, random.randint(0, 59))
                        cls.pulse(count=1, custom_datetime=order_dt, status='Delivered')
                        total_created += 1

            # 2. Check today's current order pace
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT COUNT(*) as cnt FROM orders WHERE order_date >= CURRENT_DATE")
                    today_row = cursor.fetchone()
                    today_orders = int(today_row['cnt'] if isinstance(today_row, dict) else today_row[0]) if today_row else 0

            # Target today's count based on current hour
            current_hour = now.hour
            if current_hour < 8:
                target_today = 0
            elif current_hour < 12:
                target_today = random.randint(2, 4)
            elif current_hour < 17:
                target_today = random.randint(4, 7)
            else:
                target_today = random.randint(7, 12)

            if today_orders < target_today:
                orders_to_add = target_today - today_orders
                for _ in range(orders_to_add):
                    # Pick an hour between 8 AM and current hour
                    start_h = 8 if current_hour >= 8 else current_hour
                    h = random.randint(start_h, current_hour)
                    m = random.randint(0, 59 if h < current_hour else now.minute)
                    order_dt = datetime(now.year, now.month, now.day, h, m, random.randint(0, 59))
                    cls.pulse(count=1, custom_datetime=order_dt, status='Delivered')
                    total_created += 1

        except Exception as e:
            logger.error(f"Error ensuring daily traffic activity: {e}")

        cls._last_activity_check = time.time()
        return total_created

    @classmethod
    def check_heartbeat_on_request(cls) -> None:
        """
        Lightweight check called during web requests.
        Ensures catch-up runs at most once every 30 minutes in a non-blocking thread.
        """
        now = time.time()
        # Only run if 30 minutes have elapsed since last check
        if now - cls._last_activity_check > 1800:
            cls._last_activity_check = now
            threading.Thread(target=cls.ensure_daily_activity, daemon=True, name="traffic-catchup-worker").start()

    @classmethod
    def start_daemon(cls, app: Optional[Any] = None) -> None:
        """
        Starts the background autonomous quick-commerce traffic generator daemon thread.
        """
        with cls._daemon_lock:
            if cls._daemon_started:
                return
            cls._daemon_started = True

        def _worker_loop():
            logger.info("⚡ Autonomous Quick-Commerce Traffic Daemon started.")
            # Run initial catch-up check after short delay
            time.sleep(5)
            try:
                cls.ensure_daily_activity()
            except Exception as ex:
                logger.warning(f"Initial traffic catch-up warning: {ex}")

            while True:
                try:
                    # Sleep 15 minutes between periodic traffic checks
                    time.sleep(900)

                    now = datetime.now()
                    hour = now.hour

                    # Active retail operating hours: 08:00 AM to 22:30 PM
                    if 8 <= hour <= 22:
                        # Higher probability during breakfast & dinner rushes
                        is_rush = (8 <= hour <= 10) or (18 <= hour <= 21)
                        prob = 0.85 if is_rush else 0.50

                        if random.random() < prob:
                            created = cls.pulse(count=1, status='Delivered')
                            if created:
                                logger.info(f"⚡ Autonomous pulse: Order #{created[0]['order_id']} dispatched in {created[0]['city']} (₹{created[0]['total_amount']:.2f})")

                except Exception as loop_err:
                    logger.error(f"Traffic daemon loop exception: {loop_err}")
                    time.sleep(60)

        worker = threading.Thread(target=_worker_loop, daemon=True, name="daily-drop-traffic-daemon")
        worker.start()
