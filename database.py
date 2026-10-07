"""
Database module for handling all PostgreSQL operations with Neon.

This module provides high-performance connection pooling (psycopg2.pool.ThreadedConnectionPool),
initialization, and helper functions for CRUD operations with parameterized queries
and proper resource cleanup.
"""

import os
import time
import json
import logging
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timedelta
from contextlib import contextmanager

import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from werkzeug.security import generate_password_hash

from config import Config


# Configure logging
logger = logging.getLogger(__name__)


class DatabaseError(Exception):
    """Custom exception for database operations."""
    pass


# Global connection pool for ultra-fast connection reuse with Neon
_db_pool: Optional[pool.ThreadedConnectionPool] = None


def get_pool() -> pool.ThreadedConnectionPool:
    """
    Get or initialize the threaded connection pool for Neon PostgreSQL.
    """
    global _db_pool
    if _db_pool is None or _db_pool.closed:
        try:
            _db_pool = pool.ThreadedConnectionPool(
                minconn=Config.DB_MIN_CONN,
                maxconn=Config.DB_MAX_CONN,
                dsn=Config.DATABASE_URL
            )
            logger.info("Initialized Neon PostgreSQL connection pool.")
        except Exception as e:
            logger.error(f"Failed to create Neon PostgreSQL connection pool: {e}")
            raise DatabaseError(f"Database connection pool error: {e}") from e
    return _db_pool


@contextmanager
def get_db_connection():
    """
    Context manager for database connections using the connection pool.

    Yields:
        psycopg2.extensions.connection: Pooled database connection.

    Raises:
        DatabaseError: If acquiring connection or executing transaction fails.
    """
    p = get_pool()
    conn = None
    try:
        conn = p.getconn()
        conn.autocommit = False
        yield conn
        conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Database error during transaction: {e}")
        raise DatabaseError(f"Database error: {e}") from e
    finally:
        if conn and not conn.closed:
            p.putconn(conn)


_IS_DB_INITIALIZED = False


def init_database() -> None:
    """
    Initialize database schema and indexes on Neon PostgreSQL once.
    """
    global _IS_DB_INITIALIZED
    if _IS_DB_INITIALIZED:
        return

    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                # 1. users table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS users (
                        id SERIAL PRIMARY KEY,
                        name VARCHAR(255) NOT NULL,
                        email VARCHAR(255) UNIQUE NOT NULL,
                        password TEXT NOT NULL,
                        role VARCHAR(50) DEFAULT 'customer',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                ''')

                # 2. products table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS products (
                        product_id SERIAL PRIMARY KEY,
                        name VARCHAR(255) NOT NULL,
                        price NUMERIC(10, 2) NOT NULL,
                        category VARCHAR(100) NOT NULL,
                        subcategory VARCHAR(100),
                        image_path TEXT NOT NULL,
                        description TEXT,
                        stock INTEGER DEFAULT 50
                    );
                ''')

                # 3. orders table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS orders (
                        order_id SERIAL PRIMARY KEY,
                        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                        full_name VARCHAR(255) NOT NULL,
                        phone_number VARCHAR(50) NOT NULL,
                        address TEXT NOT NULL,
                        products_ordered TEXT NOT NULL,
                        total_amount NUMERIC(10, 2) NOT NULL,
                        status VARCHAR(50) DEFAULT 'Processing',
                        payment_method VARCHAR(50) DEFAULT 'COD',
                        payment_id VARCHAR(255),
                        order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                    ALTER TABLE orders ADD COLUMN IF NOT EXISTS payment_method VARCHAR(50) DEFAULT 'COD';
                    ALTER TABLE orders ADD COLUMN IF NOT EXISTS payment_id VARCHAR(255);
                ''')

                # 3b. order_items table (Normalized relational items)
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS order_items (
                        id SERIAL PRIMARY KEY,
                        order_id INTEGER NOT NULL REFERENCES orders(order_id) ON DELETE CASCADE,
                        product_id INTEGER REFERENCES products(product_id) ON DELETE SET NULL,
                        product_name VARCHAR(255) NOT NULL,
                        price NUMERIC(10, 2) NOT NULL,
                        quantity INTEGER NOT NULL DEFAULT 1,
                        image_path TEXT,
                        subtotal NUMERIC(10, 2) NOT NULL
                    );
                ''')

                # 3c. pending_orders table (Webhook recovery for client disconnects)
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS pending_orders (
                        id SERIAL PRIMARY KEY,
                        razorpay_order_id VARCHAR(255) UNIQUE NOT NULL,
                        user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                        full_name VARCHAR(255) NOT NULL,
                        phone_number VARCHAR(50) NOT NULL,
                        address TEXT NOT NULL,
                        products_data TEXT NOT NULL,
                        total_amount NUMERIC(10, 2) NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                ''')

                # 4. contact_messages table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS contact_messages (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                        name VARCHAR(255) NOT NULL,
                        email VARCHAR(255) NOT NULL,
                        phone VARCHAR(50),
                        subject VARCHAR(255) NOT NULL,
                        message TEXT NOT NULL,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                ''')

                # 5. wishlist table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS wishlist (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                        product_id INTEGER NOT NULL REFERENCES products(product_id) ON DELETE CASCADE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(user_id, product_id)
                    );
                ''')

                # 6. outbox_events table (Transactional Outbox Pattern)
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS outbox_events (
                        id SERIAL PRIMARY KEY,
                        event_id VARCHAR(64) UNIQUE NOT NULL,
                        event_type VARCHAR(100) NOT NULL,
                        aggregate_type VARCHAR(100) NOT NULL,
                        aggregate_id VARCHAR(100) NOT NULL,
                        payload TEXT NOT NULL,
                        status VARCHAR(50) DEFAULT 'PENDING',
                        retry_count INTEGER DEFAULT 0,
                        error_message TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        processed_at TIMESTAMP
                    );
                ''')

                # Performance indexes for fast lookups
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_products_category ON products(category);
                    CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id);
                    CREATE INDEX IF NOT EXISTS idx_orders_date ON orders(order_date);
                    CREATE INDEX IF NOT EXISTS idx_order_items_order_id ON order_items(order_id);
                    CREATE INDEX IF NOT EXISTS idx_order_items_product_id ON order_items(product_id);
                    CREATE INDEX IF NOT EXISTS idx_pending_orders_rzp_id ON pending_orders(razorpay_order_id);
                    CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
                    CREATE INDEX IF NOT EXISTS idx_wishlist_user_id ON wishlist(user_id);
                    CREATE INDEX IF NOT EXISTS idx_wishlist_product_id ON wishlist(product_id);
                    CREATE INDEX IF NOT EXISTS idx_outbox_status_created ON outbox_events(status, created_at);
                    CREATE INDEX IF NOT EXISTS idx_outbox_event_id ON outbox_events(event_id);
                ''')

                # Seed admin user if needed
                admin_hashed_password = generate_password_hash('Dailydrop@173')
                cursor.execute(
                    "SELECT id FROM users WHERE role = 'admin' OR email = %s OR email = %s",
                    ('admin_dailydrop@gmail.com', 'admin@dailydrop.com')
                )
                admin_user = cursor.fetchone()
                if not admin_user:
                    cursor.execute('''
                        INSERT INTO users (name, email, password, role)
                        VALUES ('Admin User', 'admin_dailydrop@gmail.com', %s, 'admin')
                    ''', (admin_hashed_password,))

                # Seed demo customer if needed
                demo_hashed_password = generate_password_hash('Demouser@123')
                cursor.execute("SELECT id FROM users WHERE email = %s", ('demo_dailydrop@gmail.com',))
                demo_user = cursor.fetchone()
                if not demo_user:
                    cursor.execute('''
                        INSERT INTO users (name, email, password, role)
                        VALUES ('Demo Customer', 'demo_dailydrop@gmail.com', %s, 'customer')
                    ''', (demo_hashed_password,))

                # Seed products catalog if empty
                cursor.execute("SELECT COUNT(*) as count FROM products")
                row = cursor.fetchone()
                product_count = row['count'] if row else 0
                if product_count == 0:
                    js_file_path = os.path.join(os.path.dirname(__file__), 'static', 'js', 'products.js')
                    if os.path.exists(js_file_path):
                        try:
                            with open(js_file_path, 'r', encoding='utf-8') as f:
                                content = f.read()
                            start = content.find('[')
                            end = content.rfind(']') + 1
                            if start != -1 and end != -1:
                                raw_products = json.loads(content[start:end])
                                for pid, p in enumerate(raw_products, start=1):
                                    unique_stock = 30 + ((pid * 7) % 65)
                                    cursor.execute('''
                                        INSERT INTO products (product_id, name, price, category, subcategory, image_path, description, stock)
                                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                                        ON CONFLICT (product_id) DO NOTHING
                                    ''', (
                                        pid,
                                        p.get('title', 'Product'),
                                        float(p.get('price', 0)),
                                        p.get('category', 'Grocery'),
                                        p.get('subcategory', ''),
                                        p.get('image', '/static/logo.webp'),
                                        p.get('description', ''),
                                        unique_stock
                                    ))
                                try:
                                    cursor.execute("SELECT setval(pg_get_serial_sequence('products', 'product_id'), COALESCE(MAX(product_id), 1)) FROM products;")
                                except Exception:
                                    pass
                                logger.info(f"Seeded {len(raw_products)} products into Neon PostgreSQL from products.js")
                        except Exception as e:
                            logger.error(f"Error seeding products from products.js: {e}")

                # Backfill legacy orders into normalized order_items table if empty
                try:
                    cursor.execute("SELECT COUNT(*) as count FROM order_items")
                    oi_row = cursor.fetchone()
                    oi_count = (oi_row['count'] if isinstance(oi_row, dict) else oi_row[0]) if oi_row else 0
                    if oi_count == 0:
                        cursor.execute("SELECT order_id, products_ordered FROM orders")
                        legacy_orders = cursor.fetchall()
                        for cord in legacy_orders:
                            oid = cord['order_id'] if isinstance(cord, dict) else cord[0]
                            raw_p = cord['products_ordered'] if isinstance(cord, dict) else cord[1]
                            try:
                                p_list = json.loads(raw_p) if isinstance(raw_p, str) else raw_p
                                if isinstance(p_list, list):
                                    for item in p_list:
                                        p_name = item.get('name', 'Product')
                                        p_price = float(item.get('price', 0))
                                        p_qty = int(item.get('quantity', 1))
                                        p_sub = round(p_price * p_qty, 2)
                                        p_img = item.get('image') or item.get('image_path') or '/static/logo1.webp'
                                        p_id = item.get('product_id') or item.get('id')
                                        cursor.execute('''
                                            INSERT INTO order_items (order_id, product_id, product_name, price, quantity, image_path, subtotal)
                                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                                        ''', (oid, p_id, p_name, p_price, p_qty, p_img, p_sub))
                            except Exception:
                                pass
                        logger.info("Backfilled legacy order items into normalized order_items table.")
                except Exception as oi_err:
                    logger.warning(f"Note on order_items table backfill check: {oi_err}")

        # Pre-warm product master cache, analytics, and demo/admin user accounts
        try:
            get_all_products()
            get_unified_analytics(days=30)
            get_user_by_email('admin_dailydrop@gmail.com')
            get_user_by_email('demo_dailydrop@gmail.com')
            logger.info("Product, analytics, and user cache pre-warmed for instant sub-millisecond responses.")
        except Exception as e:
            logger.warning(f"Could not pre-warm cache: {e}")

        _IS_DB_INITIALIZED = True
        logger.info("Neon PostgreSQL initialized successfully with schema, indexes, and catalog products.")
    except Exception as e:
        logger.error(f"Failed to initialize Neon database: {e}")
        raise DatabaseError(f"Failed to initialize database: {e}") from e


_USER_EMAIL_CACHE: Dict[str, Tuple[float, Dict[str, Any]]] = {}
_USER_ID_CACHE: Dict[int, Tuple[float, Dict[str, Any]]] = {}
_USER_CACHE_TTL = 300.0  # 5 minutes in-memory cache


def clear_user_cache(email: Optional[str] = None, user_id: Optional[int] = None) -> None:
    """Clear cached user records when modifications occur."""
    if email:
        _USER_EMAIL_CACHE.pop(email.lower().strip(), None)
    if user_id:
        _USER_ID_CACHE.pop(user_id, None)
    if not email and not user_id:
        _USER_EMAIL_CACHE.clear()
        _USER_ID_CACHE.clear()


def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    """Retrieve a user by email address with instant sub-millisecond memory caching."""
    if not email:
        return None
    normalized_email = email.lower().strip()
    now = time.time()
    if normalized_email in _USER_EMAIL_CACHE:
        cached_time, user = _USER_EMAIL_CACHE[normalized_email]
        if now - cached_time < _USER_CACHE_TTL:
            return user

    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute('SELECT * FROM users WHERE LOWER(email) = LOWER(%s)', (normalized_email,))
                result = cursor.fetchone()
                if result:
                    user_dict = dict(result)
                    _USER_EMAIL_CACHE[normalized_email] = (now, user_dict)
                    _USER_ID_CACHE[user_dict['id']] = (now, user_dict)
                    return user_dict
                return None
    except Exception as e:
        logger.error(f"Error retrieving user by email: {e}")
        if normalized_email in _USER_EMAIL_CACHE:
            return _USER_EMAIL_CACHE[normalized_email][1]
        raise DatabaseError(f"Failed to retrieve user: {e}") from e


def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    """Retrieve a user by ID with instant in-memory caching."""
    if not user_id:
        return None
    now = time.time()
    if user_id in _USER_ID_CACHE:
        cached_time, user = _USER_ID_CACHE[user_id]
        if now - cached_time < _USER_CACHE_TTL:
            return user

    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute('SELECT * FROM users WHERE id = %s', (user_id,))
                result = cursor.fetchone()
                if result:
                    user_dict = dict(result)
                    _USER_ID_CACHE[user_id] = (now, user_dict)
                    if user_dict.get('email'):
                        _USER_EMAIL_CACHE[user_dict['email'].lower().strip()] = (now, user_dict)
                    return user_dict
                return None
    except Exception as e:
        logger.error(f"Error retrieving user by ID: {e}")
        if user_id in _USER_ID_CACHE:
            return _USER_ID_CACHE[user_id][1]
        raise DatabaseError(f"Failed to retrieve user: {e}") from e



_PRODUCT_CACHE: Dict[str, Tuple[float, List[Dict[str, Any]]]] = {}
_CACHE_TTL_SECONDS = 300.0  # 5 minutes in-memory cache for ultra-fast page loads


def clear_product_cache() -> None:
    """Clear in-memory product cache and invalidate Redis catalog cache."""
    _PRODUCT_CACHE.clear()
    try:
        from services.redis_service import RedisService
        RedisService.invalidate_catalog()
    except Exception as e:
        logger.debug(f"Redis catalog invalidation skipped: {e}")


def get_all_products(category: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieve all products, optionally filtered by category, with Redis read-through and memory caching."""
    # 1. Distributed Read-Through Redis Cache (< 2ms)
    try:
        from services.redis_service import RedisService
        cached_catalog = RedisService.get_json('catalog:all_products')
        if cached_catalog and isinstance(cached_catalog, list):
            if category:
                return [p for p in cached_catalog if p.get('category', '').lower() == category.lower()]
            return cached_catalog
    except Exception as re:
        logger.debug(f"Redis get_all_products miss/error: {re}")

    now = time.time()

    # 2. Local in-memory cache fallback (0ms)
    if '__ALL__' in _PRODUCT_CACHE:
        cached_time, all_products = _PRODUCT_CACHE['__ALL__']
        if now - cached_time < _CACHE_TTL_SECONDS:
            # Re-hydrate Redis if evicted or restarted
            try:
                from services.redis_service import RedisService
                RedisService.set_json('catalog:all_products', all_products)
            except Exception:
                pass
            if category:
                return [p for p in all_products if p.get('category', '').lower() == category.lower()]
            return all_products

    # 3. Relational PostgreSQL Database query
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute('SELECT * FROM products ORDER BY name')
                raw_products = [dict(row) for row in cursor.fetchall()]
                all_products = []
                for item in raw_products:
                    # Provide frontend alias keys
                    item['id'] = item.get('product_id')
                    item['title'] = item.get('name')
                    item['image'] = item.get('image_path')
                    all_products.append(item)

                # Hydrate in-memory cache
                _PRODUCT_CACHE['__ALL__'] = (now, all_products)

                # Hydrate Redis distributed catalog cache (TTL: 10 minutes)
                try:
                    from services.redis_service import RedisService
                    RedisService.set_json('catalog:all_products', all_products)
                except Exception:
                    pass

                if category:
                    return [p for p in all_products if p.get('category', '').lower() == category.lower()]
                return all_products
    except Exception as e:
        logger.error(f"Error retrieving products: {e}")
        if '__ALL__' in _PRODUCT_CACHE:
            all_products = _PRODUCT_CACHE['__ALL__'][1]
            if category:
                return [p for p in all_products if p.get('category', '').lower() == category.lower()]
            return all_products
        raise DatabaseError(f"Failed to retrieve products: {e}") from e


def get_product_by_id(product_id: int) -> Optional[Dict[str, Any]]:
    """Retrieve a product by ID, checking Redis and in-memory cache first."""
    # 1. Distributed Redis Cache
    try:
        from services.redis_service import RedisService
        cached_p = RedisService.get_json(f"catalog:product:{product_id}")
        if cached_p and isinstance(cached_p, dict):
            return cached_p
    except Exception:
        pass

    # 2. Local memory cache
    for _, (_, products) in _PRODUCT_CACHE.items():
        for p in products:
            if p.get('product_id') == product_id:
                return p

    # 3. Database query
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute('SELECT * FROM products WHERE product_id = %s', (product_id,))
                result = cursor.fetchone()
                if result:
                    item = dict(result)
                    item['id'] = item.get('product_id')
                    item['title'] = item.get('name')
                    item['image'] = item.get('image_path')
                    try:
                        from services.redis_service import RedisService
                        RedisService.set_json(f"catalog:product:{product_id}", item, ttl=600)
                    except Exception:
                        pass
                    return item
                return None
    except Exception as e:
        logger.error(f"Error retrieving product: {e}")
        raise DatabaseError(f"Failed to retrieve product: {e}") from e


_ANALYTICS_CACHE: Dict[str, Tuple[float, Dict[str, Any]]] = {}
_ANALYTICS_TTL_SECONDS = 30.0  # 30 seconds in-memory cache for ultra-fast, responsive dashboard


def clear_analytics_cache() -> None:
    """Clear in-memory analytics cache when orders/messages/products change."""
    _ANALYTICS_CACHE.clear()


def get_unified_analytics(days: int = 30) -> Dict[str, Any]:
    """
    Retrieve all dashboard stats, 30-day sales data, category revenue breakdown,
    and hourly order distributions in ONE single combined SQL transaction with in-memory caching.
    """
    now = time.time()
    cache_key = f"unified_{days}"
    if cache_key in _ANALYTICS_CACHE:
        cached_time, cached_data = _ANALYTICS_CACHE[cache_key]
        if now - cached_time < _ANALYTICS_TTL_SECONDS:
            return cached_data

    # Generate date labels for chart
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days - 1)
    date_list = []
    current_date = start_date
    while current_date <= end_date:
        date_list.append(current_date.strftime('%Y-%m-%d'))
        current_date += timedelta(days=1)

    try:
        # Pre-build product->category map from in-memory catalog (0ms)
        all_products = get_all_products()
        prod_cat_map = {p['name'].lower(): p.get('category', 'Grocery') for p in all_products}

        category_totals = {
            'Grocery': 0.0,
            'Vegetables': 0.0,
            'Dairy & Breakfast': 0.0,
            'Snacks': 0.0,
            'Beverages': 0.0,
            'Frozen Foods': 0.0,
            'Household': 0.0,
            'Home & Kitchen': 0.0,
            'Personal Care': 0.0,
            'Baby Care': 0.0
        }

        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute('''
                    SELECT 
                        (SELECT COUNT(*) FROM orders) AS total_orders,
                        (SELECT COUNT(*) FROM users) AS total_users,
                        (SELECT COUNT(*) FROM products) AS total_products,
                        (SELECT COUNT(*) FROM contact_messages) AS total_contacts,
                        (SELECT COALESCE(SUM(total_amount), 0) FROM orders) AS total_revenue,
                        (
                            SELECT COALESCE(json_agg(s), '[]'::json) FROM (
                                SELECT order_date::date::text as sale_date, SUM(total_amount) as daily_total
                                FROM orders
                                WHERE order_date::date >= CURRENT_DATE - INTERVAL '30 days'
                                GROUP BY sale_date
                                ORDER BY sale_date
                            ) s
                        ) AS sales_rows,
                        (
                            SELECT COALESCE(json_agg(h), '[]'::json) FROM (
                                SELECT TO_CHAR(order_date, 'HH24') as order_hour, COUNT(*) as count
                                FROM orders
                                GROUP BY order_hour
                            ) h
                        ) AS hourly_rows,
                        (
                            SELECT COALESCE(json_agg(o.products_ordered), '[]'::json) FROM orders o
                        ) AS orders_products;
                ''')
                row = cursor.fetchone()

                total_orders = int(row['total_orders'] or 0)
                total_revenue = float(row['total_revenue'] or 0.0)
                avg_order_value = round(total_revenue / total_orders, 2) if total_orders > 0 else 0.0

                # Process sales data
                sales_dict = {str(item['sale_date']): float(item['daily_total'] or 0) for item in (row['sales_rows'] or [])}
                sales_data = [sales_dict.get(date, 0.0) for date in date_list]

                # Process hourly distribution
                hour_counts = {f"{h:02d}:00": 0 for h in range(24)}
                for h in (row['hourly_rows'] or []):
                    if h.get('order_hour') is not None:
                        h_str = f"{int(h['order_hour']):02d}:00"
                        hour_counts[h_str] = int(h['count'])

                # Process category totals in memory
                for raw_items in (row['orders_products'] or []):
                    try:
                        items = json.loads(raw_items) if isinstance(raw_items, str) else raw_items
                        if not isinstance(items, list):
                            continue
                        for item in items:
                            name = (item.get('name') or '').lower()
                            price = float(item.get('price', 0))
                            qty = int(item.get('quantity', 1))
                            cat = prod_cat_map.get(name, 'Grocery')
                            category_totals[cat] = round(category_totals.get(cat, 0.0) + (price * qty), 2)
                    except Exception:
                        continue

                analytics_result = {
                    'stats': {
                        'total_orders': total_orders,
                        'total_users': int(row['total_users'] or 0),
                        'total_products': int(row['total_products'] or 0),
                        'total_contacts': int(row['total_contacts'] or 0),
                        'total_revenue': total_revenue,
                        'avg_order_value': avg_order_value,
                    },
                    'sales': {
                        'labels': date_list,
                        'data': sales_data,
                        'min_date': start_date.strftime('%Y-%m-%d'),
                        'max_date': end_date.strftime('%Y-%m-%d')
                    },
                    'categories': category_totals,
                    'hourly': hour_counts
                }

                _ANALYTICS_CACHE[cache_key] = (now, analytics_result)
                return analytics_result
    except Exception as e:
        logger.warning(f"Combined SQL analytics query failed, using relational fallback: {e}")
        try:
            with get_db_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute("SELECT COUNT(*) as c FROM orders")
                    r_ord = cursor.fetchone()
                    total_orders = int(r_ord['c'] if isinstance(r_ord, dict) else r_ord[0]) if r_ord else 0

                    cursor.execute("SELECT COUNT(*) as c FROM users")
                    r_usr = cursor.fetchone()
                    total_users = int(r_usr['c'] if isinstance(r_usr, dict) else r_usr[0]) if r_usr else 0

                    cursor.execute("SELECT COUNT(*) as c FROM products")
                    r_prd = cursor.fetchone()
                    total_products = int(r_prd['c'] if isinstance(r_prd, dict) else r_prd[0]) if r_prd else 0

                    cursor.execute("SELECT COUNT(*) as c FROM contact_messages")
                    r_cnt = cursor.fetchone()
                    total_contacts = int(r_cnt['c'] if isinstance(r_cnt, dict) else r_cnt[0]) if r_cnt else 0

                    cursor.execute("SELECT COALESCE(SUM(total_amount), 0) as s FROM orders")
                    r_rev = cursor.fetchone()
                    total_revenue = float(r_rev['s'] if isinstance(r_rev, dict) else r_rev[0]) if r_rev else 0.0

                    avg_order_value = round(total_revenue / total_orders, 2) if total_orders > 0 else 0.0

                    cursor.execute("SELECT order_date, total_amount, products_ordered FROM orders")
                    all_ord_rows = cursor.fetchall()

                    sales_dict = {}
                    hour_counts = {f"{h:02d}:00": 0 for h in range(24)}
                    for orow in all_ord_rows:
                        odate = orow.get('order_date') if isinstance(orow, dict) else orow[0]
                        otot = orow.get('total_amount') if isinstance(orow, dict) else orow[1]
                        oprod = orow.get('products_ordered') if isinstance(orow, dict) else orow[2]
                        if odate:
                            dt_str = str(odate)[:10]
                            sales_dict[dt_str] = round(sales_dict.get(dt_str, 0.0) + float(otot or 0), 2)
                            try:
                                h_int = int(str(odate)[11:13]) if len(str(odate)) >= 13 else 0
                                h_str = f"{h_int:02d}:00"
                                hour_counts[h_str] = hour_counts.get(h_str, 0) + 1
                            except Exception:
                                pass
                        try:
                            items = json.loads(oprod) if isinstance(oprod, str) else oprod
                            if isinstance(items, list):
                                for item in items:
                                    name = (item.get('name') or '').lower()
                                    price = float(item.get('price', 0))
                                    qty = int(item.get('quantity', 1))
                                    cat = prod_cat_map.get(name, 'Grocery')
                                    category_totals[cat] = round(category_totals.get(cat, 0.0) + (price * qty), 2)
                        except Exception:
                            pass

                    sales_data = [sales_dict.get(date, 0.0) for date in date_list]

                    analytics_result = {
                        'stats': {
                            'total_orders': total_orders,
                            'total_users': total_users,
                            'total_products': total_products,
                            'total_contacts': total_contacts,
                            'total_revenue': total_revenue,
                            'avg_order_value': avg_order_value,
                        },
                        'sales': {
                            'labels': date_list,
                            'data': sales_data,
                            'min_date': start_date.strftime('%Y-%m-%d'),
                            'max_date': end_date.strftime('%Y-%m-%d')
                        },
                        'categories': category_totals,
                        'hourly': hour_counts
                    }
                    _ANALYTICS_CACHE[cache_key] = (now, analytics_result)
                    return analytics_result
        except Exception as fallback_e:
            logger.error(f"Fallback analytics calculation error: {fallback_e}")
            if cache_key in _ANALYTICS_CACHE:
                return _ANALYTICS_CACHE[cache_key][1]
            return {}


def get_dashboard_stats() -> Dict[str, Any]:
    """Retrieve dashboard statistics from unified analytics."""
    analytics = get_unified_analytics(days=30)
    return analytics.get('stats', {
        'total_orders': 0,
        'total_users': 0,
        'total_products': 0,
        'total_contacts': 0,
        'total_revenue': 0.0,
        'avg_order_value': 0.0
    })


def get_sales_data(days: int = 30) -> Dict[str, Any]:
    """Retrieve sales data from unified analytics."""
    analytics = get_unified_analytics(days=days)
    return analytics.get('sales', {
        'labels': [],
        'data': [],
        'min_date': '',
        'max_date': ''
    })



def update_product_price(product_id: int, price: float) -> bool:
    """Update a product's price."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute('UPDATE products SET price = %s WHERE product_id = %s', (price, product_id))
                updated = cursor.rowcount > 0
                if updated:
                    clear_product_cache()
                return updated
    except Exception as e:
        logger.error(f"Error updating product price: {e}")
        raise DatabaseError(f"Failed to update product price: {e}") from e


def update_product_stock(product_id: int, stock: int) -> bool:
    """Update a product's stock quantity."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute('UPDATE products SET stock = %s WHERE product_id = %s', (stock, product_id))
                updated = cursor.rowcount > 0
                if updated:
                    clear_product_cache()
                    try:
                        from services.redis_service import RedisService
                        RedisService.set_stock(product_id, stock)
                    except Exception:
                        pass
                return updated
    except Exception as e:
        logger.error(f"Error updating product stock: {e}")
        raise DatabaseError(f"Failed to update product stock: {e}") from e


def add_product(name: str, price: float, category: str, subcategory: str = '',
                image_path: str = '/static/logo.webp', description: str = '', stock: int = 50) -> int:
    """Add a new product to the database catalog."""
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute('''
                    INSERT INTO products (name, price, category, subcategory, image_path, description, stock)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING product_id
                ''', (name, price, category, subcategory, image_path, description, stock))
                row = cursor.fetchone()
                clear_product_cache()
                if row:
                    pid = row['product_id']
                    try:
                        from services.redis_service import RedisService
                        RedisService.set_stock(pid, stock)
                    except Exception:
                        pass
                    return pid
                return None
    except Exception as e:
        logger.error(f"Error adding new product: {e}")
        raise DatabaseError(f"Failed to add product: {e}") from e


def delete_product(product_id: int) -> bool:
    """Delete a product by ID."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute('DELETE FROM products WHERE product_id = %s', (product_id,))
                deleted = cursor.rowcount > 0
                if deleted:
                    clear_product_cache()
                    try:
                        from services.redis_service import RedisService
                        RedisService.delete(RedisService.stock_key(product_id))
                    except Exception:
                        pass
                return deleted
    except Exception as e:
        logger.error(f"Error deleting product: {e}")
        raise DatabaseError(f"Failed to delete product: {e}") from e


def get_low_stock_products(threshold: int = 10) -> List[Dict[str, Any]]:
    """Retrieve products where stock is equal to or below the given threshold using in-memory catalog."""
    try:
        all_products = get_all_products()
        return [p for p in all_products if (p.get('stock') or 50) <= threshold]
    except Exception as e:
        logger.error(f"Error retrieving low stock products: {e}")
        return []


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


def get_category_revenue() -> Dict[str, float]:
    """Retrieve total sales revenue broken down by product category in 0ms using in-memory product mapping."""
    try:
        # Pre-build product-to-category lookup map in memory (0ms)
        all_products = get_all_products()
        prod_cat_map = {p['name'].lower(): p.get('category', 'Grocery') for p in all_products}

        category_totals = {
            'Grocery': 0.0,
            'Vegetables': 0.0,
            'Dairy & Breakfast': 0.0,
            'Snacks': 0.0,
            'Beverages': 0.0,
            'Frozen Foods': 0.0,
            'Household': 0.0,
            'Home & Kitchen': 0.0,
            'Personal Care': 0.0,
            'Baby Care': 0.0
        }

        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute('SELECT products_ordered FROM orders')
                rows = cursor.fetchall()

                for row in rows:
                    try:
                        raw_items = row['products_ordered']
                        items = json.loads(raw_items) if isinstance(raw_items, str) else raw_items
                        if not isinstance(items, list):
                            continue
                        for item in items:
                            name = (item.get('name') or '').lower()
                            price = float(item.get('price', 0))
                            qty = int(item.get('quantity', 1))
                            cat = prod_cat_map.get(name, 'Grocery')
                            category_totals[cat] = round(category_totals.get(cat, 0.0) + (price * qty), 2)
                    except Exception:
                        continue

                return category_totals
    except Exception as e:
        logger.error(f"Error retrieving category revenue: {e}")
        return {}


def get_hourly_order_distribution() -> Dict[str, int]:
    """Retrieve order volume across hours of the day (00:00 - 23:00)."""
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute('''
                    SELECT TO_CHAR(order_date, 'HH24') as order_hour, COUNT(*) as count
                    FROM orders
                    GROUP BY order_hour
                ''')
                rows = cursor.fetchall()
                hour_counts = {f"{h:02d}:00": 0 for h in range(24)}
                for r in rows:
                    if r['order_hour'] is not None:
                        h_str = f"{int(r['order_hour']):02d}:00"
                        hour_counts[h_str] = int(r['count'])
                return hour_counts
    except Exception as e:
        logger.error(f"Error retrieving hourly distribution: {e}")
        return {}


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
                       phone_number: str, address: str, products: Any, total_amount: float) -> bool:
    """Save pending order details to handle client disconnects during payment."""
    try:
        products_json = json.dumps(products) if not isinstance(products, str) else products
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                try:
                    cursor.execute('''
                        INSERT INTO pending_orders (razorpay_order_id, user_id, full_name, phone_number, address, products_data, total_amount)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (razorpay_order_id) DO UPDATE SET
                            full_name = EXCLUDED.full_name,
                            phone_number = EXCLUDED.phone_number,
                            address = EXCLUDED.address,
                            products_data = EXCLUDED.products_data,
                            total_amount = EXCLUDED.total_amount
                    ''', (razorpay_order_id, user_id, full_name, phone_number, address, products_json, total_amount))
                except Exception:
                    # Fallback for environments or SQLite without ON CONFLICT DO UPDATE
                    cursor.execute('DELETE FROM pending_orders WHERE razorpay_order_id = %s', (razorpay_order_id,))
                    cursor.execute('''
                        INSERT INTO pending_orders (razorpay_order_id, user_id, full_name, phone_number, address, products_data, total_amount)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ''', (razorpay_order_id, user_id, full_name, phone_number, address, products_json, total_amount))
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

