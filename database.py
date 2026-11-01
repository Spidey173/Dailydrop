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
    Adapts pool size automatically for serverless environments (e.g. Vercel)
    to minimize TCP/TLS handshakes and speed up cold starts.
    """
    global _db_pool
    if _db_pool is None or _db_pool.closed:
        try:
            is_serverless = bool(os.getenv('VERCEL') or os.getenv('AWS_LAMBDA_FUNCTION_NAME'))
            minconn = 1 if is_serverless else Config.DB_MIN_CONN
            maxconn = 3 if is_serverless else Config.DB_MAX_CONN

            _db_pool = pool.ThreadedConnectionPool(
                minconn=minconn,
                maxconn=maxconn,
                dsn=Config.DATABASE_URL
            )
            logger.info(f"Initialized Neon PostgreSQL connection pool (minconn={minconn}, maxconn={maxconn}).")
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
        # Verify connection is open; discard stale socket closed by Neon serverless compute sleep
        if conn and conn.closed != 0:
            try:
                p.putconn(conn, close=True)
            except Exception:
                pass
            conn = p.getconn()

        conn.autocommit = False
        yield conn
        conn.commit()
    except Exception as e:
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
            # If broken or disconnected, discard from pool so subsequent requests get a fresh socket
            try:
                p.putconn(conn, close=True)
                conn = None
            except Exception:
                pass
        logger.error(f"Database error during transaction: {e}")
        raise DatabaseError(f"Database error: {e}") from e
    finally:
        if conn and not conn.closed:
            p.putconn(conn)


_IS_DB_INITIALIZED = False


def init_database() -> None:
    """
    Initialize database schema and indexes on Neon PostgreSQL once.
    Uses an ultra-fast check to skip heavy DDL/seeding if already initialized.
    """
    global _IS_DB_INITIALIZED
    if _IS_DB_INITIALIZED:
        return

    # Fast-path: Check if database tables already exist and are populated
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1 FROM products LIMIT 1")
                row = cursor.fetchone()
                if row:
                    _IS_DB_INITIALIZED = True
                    try:
                        get_all_products()
                    except Exception:
                        pass
                    logger.info("⚡ Neon database schema and catalog verified. Fast-path startup active.")
                    return
    except Exception as check_err:
        logger.info(f"Schema verification note ({check_err}). Performing full schema initialization...")

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
                        city VARCHAR(100) DEFAULT 'Bangalore',
                        delivery_duration_minutes NUMERIC(4, 1) DEFAULT 7.5,
                        products_ordered TEXT NOT NULL,
                        total_amount NUMERIC(10, 2) NOT NULL,
                        status VARCHAR(50) DEFAULT 'Processing',
                        payment_method VARCHAR(50) DEFAULT 'COD',
                        payment_id VARCHAR(255),
                        order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                    ALTER TABLE orders ADD COLUMN IF NOT EXISTS payment_method VARCHAR(50) DEFAULT 'COD';
                    ALTER TABLE orders ADD COLUMN IF NOT EXISTS payment_id VARCHAR(255);
                    ALTER TABLE orders ADD COLUMN IF NOT EXISTS city VARCHAR(100) DEFAULT 'Bangalore';
                    ALTER TABLE orders ADD COLUMN IF NOT EXISTS delivery_duration_minutes NUMERIC(4, 1) DEFAULT 7.5;
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
                        city VARCHAR(100) DEFAULT 'Bangalore',
                        products_data TEXT NOT NULL,
                        total_amount NUMERIC(10, 2) NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                    ALTER TABLE pending_orders ADD COLUMN IF NOT EXISTS city VARCHAR(100) DEFAULT 'Bangalore';
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
                                        p.get('image', '/static/product-placeholder.svg'),
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

        # Pre-warm product master cache and demo/admin user accounts (skip expensive analytics on serverless cold starts)
        try:
            get_all_products()
            get_user_by_email('admin_dailydrop@gmail.com')
            get_user_by_email('demo_dailydrop@gmail.com')
            if not os.getenv('VERCEL'):
                get_unified_analytics(days=30)
            logger.info("Product and user cache pre-warmed for fast responses.")
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

CATEGORY_CANONICAL_MAP = {
    'vegetables': 'Fruits & Vegetables',
    'fruits': 'Fruits & Vegetables',
    'fruits & vegetables': 'Fruits & Vegetables',
    'fruits and vegetables': 'Fruits & Vegetables',
    'fruits_vegetables': 'Fruits & Vegetables',
    'produce': 'Fruits & Vegetables',
    'fruit & vegetable': 'Fruits & Vegetables',

    'dairy': 'Dairy & Breakfast',
    'dairy & breakfast': 'Dairy & Breakfast',
    'dairy and breakfast': 'Dairy & Breakfast',
    'dairy_breakfast': 'Dairy & Breakfast',
    'breakfast': 'Dairy & Breakfast',

    'household': 'Household',
    'household items': 'Household',
    'household_items': 'Household',

    'home & kitchen': 'Home & Kitchen',
    'home and kitchen': 'Home & Kitchen',
    'home kitchen': 'Home & Kitchen',
    'home_kitchen': 'Home & Kitchen',
    'kitchen': 'Home & Kitchen',

    'baby care': 'Baby Care',
    'baby_care': 'Baby Care',

    'frozen foods': 'Frozen Foods',
    'frozen_foods': 'Frozen Foods',
    'frozen': 'Frozen Foods',

    'personal care': 'Personal Care',
    'personal_care': 'Personal Care',

    'grocery': 'Grocery',
    'groceries': 'Grocery',

    'beverages': 'Beverages',
    'drinks': 'Beverages',

    'snacks': 'Snacks',
}


def normalize_category(category: Optional[str]) -> str:
    """Normalize category name to standard canonical catalog name."""
    if not category:
        return 'Grocery'
    cleaned = category.strip()
    return CATEGORY_CANONICAL_MAP.get(cleaned.lower(), cleaned)


def is_matching_category(product_cat: Optional[str], target_cat: Optional[str]) -> bool:
    """Case-insensitive matching supporting category aliases & synonyms."""
    if not target_cat:
        return True
    if not product_cat:
        return False
    p_norm = normalize_category(product_cat).lower()
    t_norm = normalize_category(target_cat).lower()
    if p_norm == t_norm:
        return True
    p_raw = product_cat.lower().strip()
    t_raw = target_cat.lower().strip()
    return p_raw == t_raw or t_raw in p_raw or p_raw in t_raw


def clear_product_cache(product_id: Optional[int] = None) -> None:
    """Clear in-memory product cache and invalidate Redis catalog cache."""
    _PRODUCT_CACHE.clear()
    try:
        from services.redis_service import RedisService
        RedisService.invalidate_catalog(product_id)
    except Exception as e:
        logger.debug(f"Redis catalog invalidation skipped: {e}")


def get_all_products(category: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieve all products, optionally filtered by category, with tiered L1 (memory) and L2 (Redis) caching."""
    now = time.time()

    # 1. Local in-memory cache (L1: instant < 0.01ms)
    if '__ALL__' in _PRODUCT_CACHE:
        cached_time, all_products = _PRODUCT_CACHE['__ALL__']
        if now - cached_time < _CACHE_TTL_SECONDS:
            if category:
                return [p for p in all_products if is_matching_category(p.get('category', ''), category)]
            return all_products

    # 2. Distributed Read-Through Redis Cache (L2: distributed shared cache)
    try:
        from services.redis_service import RedisService
        cached_catalog = RedisService.get_json('catalog:all_products')
        if cached_catalog and isinstance(cached_catalog, list):
            for p in cached_catalog:
                if p.get('price') is not None:
                    try:
                        p['price'] = float(p['price'])
                    except (ValueError, TypeError):
                        pass
            # Hydrate local L1 cache
            _PRODUCT_CACHE['__ALL__'] = (now, cached_catalog)
            if category:
                return [p for p in cached_catalog if is_matching_category(p.get('category', ''), category)]
            return cached_catalog
    except Exception as re:
        logger.debug(f"Redis get_all_products miss/error: {re}")

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
                    if item.get('price') is not None:
                        try:
                            item['price'] = float(item['price'])
                        except (ValueError, TypeError):
                            pass
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
                    return [p for p in all_products if is_matching_category(p.get('category', ''), category)]
                return all_products
    except Exception as e:
        logger.error(f"Error retrieving products: {e}")
        if '__ALL__' in _PRODUCT_CACHE:
            all_products = _PRODUCT_CACHE['__ALL__'][1]
            if category:
                return [p for p in all_products if is_matching_category(p.get('category', ''), category)]
            return all_products
        raise DatabaseError(f"Failed to retrieve products: {e}") from e


def get_product_by_id(product_id: int) -> Optional[Dict[str, Any]]:
    """Retrieve a product by ID, checking local memory first, then Redis, and finally DB."""
    # 1. Local memory cache (L1: instant < 0.01ms)
    for _, (_, products) in _PRODUCT_CACHE.items():
        for p in products:
            if p.get('product_id') == product_id or p.get('id') == product_id:
                return p

    # 2. Distributed Redis Cache (L2)
    try:
        from services.redis_service import RedisService
        cached_p = RedisService.get_json(f"catalog:product:{product_id}")
        if cached_p and isinstance(cached_p, dict):
            return cached_p
    except Exception:
        pass

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
                    if item.get('price') is not None:
                        try:
                            item['price'] = float(item['price'])
                        except (ValueError, TypeError):
                            pass
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


def get_product_by_name(name: str) -> Optional[Dict[str, Any]]:
    """Retrieve a product by name (exact or case-insensitive) from database."""
    if not name or not isinstance(name, str):
        return None
    cleaned = name.strip()
    if not cleaned:
        return None

    # Check local memory cache
    for _, (_, products) in _PRODUCT_CACHE.items():
        for p in products:
            if p.get('name', '').lower() == cleaned.lower():
                return p

    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute('SELECT * FROM products WHERE LOWER(name) = LOWER(%s) LIMIT 1', (cleaned,))
                result = cursor.fetchone()
                if not result:
                    # Also try partial matching if name contains packaging specs
                    cursor.execute(
                        'SELECT * FROM products WHERE name ILIKE %s ORDER BY LENGTH(name) ASC LIMIT 1',
                        (f"%{cleaned}%",)
                    )
                    result = cursor.fetchone()
                if result:
                    item = dict(result)
                    item['id'] = item.get('product_id')
                    item['title'] = item.get('name')
                    item['image'] = item.get('image_path')
                    if item.get('price') is not None:
                        try:
                            item['price'] = float(item['price'])
                        except (ValueError, TypeError):
                            pass
                    return item
                return None
    except Exception as e:
        logger.error(f"Error retrieving product by name '{name}': {e}")
        return None



_ANALYTICS_CACHE: Dict[str, Tuple[float, Dict[str, Any]]] = {}
_ANALYTICS_TTL_SECONDS = 300.0  # 5 minutes in-memory cache for ultra-fast, responsive dashboard

_DEFAULT_CUSTOMER_PROFILES = [
    {'user_id': 101, 'name': 'Aditya Sharma', 'email': 'aditya.sharma@gmail.com', 'phone': '+91 98201 44521', 'city': 'Bangalore', 'total_orders': 28, 'total_spend': 14850.00, 'avg_order_value': 530.36, 'recency_days': 24, 'last_order_str': '2026-10-08 18:42', 'segment': 'At Risk (High Value Churn)'},
    {'user_id': 102, 'name': 'Priya Sundaram', 'email': 'priya.sundaram@outlook.com', 'phone': '+91 98450 12903', 'city': 'Bangalore', 'total_orders': 22, 'total_spend': 11920.00, 'avg_order_value': 541.82, 'recency_days': 26, 'last_order_str': '2026-10-06 20:15', 'segment': 'At Risk (High Value Churn)'},
    {'user_id': 103, 'name': 'Vikram Malhotra', 'email': 'vikram.m@gmail.com', 'phone': '+91 99100 87234', 'city': 'Delhi NCR', 'total_orders': 19, 'total_spend': 10450.00, 'avg_order_value': 550.00, 'recency_days': 22, 'last_order_str': '2026-10-10 19:30', 'segment': 'At Risk (High Value Churn)'},
    {'user_id': 104, 'name': 'Sneha Kulkarni', 'email': 'sneha.k@yahoo.com', 'phone': '+91 98220 54312', 'city': 'Pune', 'total_orders': 25, 'total_spend': 13200.00, 'avg_order_value': 528.00, 'recency_days': 28, 'last_order_str': '2026-10-04 11:20', 'segment': 'At Risk (High Value Churn)'},
    {'user_id': 105, 'name': 'Rajesh Iyer', 'email': 'rajesh.iyer@gmail.com', 'phone': '+91 98400 32190', 'city': 'Mumbai', 'total_orders': 31, 'total_spend': 16750.00, 'avg_order_value': 540.32, 'recency_days': 25, 'last_order_str': '2026-10-07 14:10', 'segment': 'At Risk (High Value Churn)'},
    {'user_id': 106, 'name': 'Ananya Verma', 'email': 'ananya.v@gmail.com', 'phone': '+91 98111 23456', 'city': 'Delhi NCR', 'total_orders': 34, 'total_spend': 18900.00, 'avg_order_value': 555.88, 'recency_days': 2, 'last_order_str': '2026-10-30 19:12', 'segment': 'Champions (VIP)'},
    {'user_id': 107, 'name': 'Kavya Nair', 'email': 'kavya.nair@gmail.com', 'phone': '+91 97400 56789', 'city': 'Bangalore', 'total_orders': 30, 'total_spend': 16400.00, 'avg_order_value': 546.67, 'recency_days': 3, 'last_order_str': '2026-10-29 18:05', 'segment': 'Champions (VIP)'},
    {'user_id': 108, 'name': 'Arjun Mehta', 'email': 'arjun.mehta@corp.in', 'phone': '+91 98210 98765', 'city': 'Mumbai', 'total_orders': 29, 'total_spend': 15600.00, 'avg_order_value': 537.93, 'recency_days': 1, 'last_order_str': '2026-10-31 21:00', 'segment': 'Champions (VIP)'},
    {'user_id': 109, 'name': 'Rohan Deshmukh', 'email': 'rohan.d@gmail.com', 'phone': '+91 98811 44321', 'city': 'Pune', 'total_orders': 27, 'total_spend': 14200.00, 'avg_order_value': 525.93, 'recency_days': 4, 'last_order_str': '2026-10-28 20:30', 'segment': 'Champions (VIP)'},
    {'user_id': 110, 'name': 'Siddharth Reddy', 'email': 'siddharth.r@tech.com', 'phone': '+91 99890 12345', 'city': 'Hyderabad', 'total_orders': 26, 'total_spend': 13950.00, 'avg_order_value': 536.54, 'recency_days': 2, 'last_order_str': '2026-10-30 17:45', 'segment': 'Champions (VIP)'},
    {'user_id': 111, 'name': 'Divya Krishnan', 'email': 'divya.k@gmail.com', 'phone': '+91 98412 87654', 'city': 'Bangalore', 'total_orders': 18, 'total_spend': 9300.00, 'avg_order_value': 516.67, 'recency_days': 5, 'last_order_str': '2026-10-27 12:15', 'segment': 'Loyal Regulars'},
    {'user_id': 112, 'name': 'Manish Gupta', 'email': 'manish.g@gmail.com', 'phone': '+91 98105 67890', 'city': 'Delhi NCR', 'total_orders': 16, 'total_spend': 8400.00, 'avg_order_value': 525.00, 'recency_days': 7, 'last_order_str': '2026-10-25 19:20', 'segment': 'Loyal Regulars'},
    {'user_id': 113, 'name': 'Meera Joshi', 'email': 'meera.joshi@gmail.com', 'phone': '+91 98230 45678', 'city': 'Pune', 'total_orders': 15, 'total_spend': 7950.00, 'avg_order_value': 530.00, 'recency_days': 6, 'last_order_str': '2026-10-26 15:30', 'segment': 'Loyal Regulars'},
    {'user_id': 114, 'name': 'Varun Hegde', 'email': 'varun.h@gmail.com', 'phone': '+91 99001 23456', 'city': 'Hyderabad', 'total_orders': 6, 'total_spend': 3250.00, 'avg_order_value': 541.67, 'recency_days': 3, 'last_order_str': '2026-10-29 14:10', 'segment': 'Recent / Promising'},
    {'user_id': 115, 'name': 'Nikhil Saxena', 'email': 'nikhil.s@gmail.com', 'phone': '+91 98188 77665', 'city': 'Delhi NCR', 'total_orders': 4, 'total_spend': 2100.00, 'avg_order_value': 525.00, 'recency_days': 35, 'last_order_str': '2026-09-27 10:05', 'segment': 'Hibernating / Lost'},
    {'user_id': 116, 'name': 'Tanvi Sethi', 'email': 'tanvi.sethi@gmail.com', 'phone': '+91 98100 45612', 'city': 'Delhi NCR', 'total_orders': 23, 'total_spend': 12100.00, 'avg_order_value': 526.09, 'recency_days': 23, 'last_order_str': '2026-10-09 16:45', 'segment': 'At Risk (High Value Churn)'},
    {'user_id': 117, 'name': 'Harish Patel', 'email': 'harish.patel@gmail.com', 'phone': '+91 98250 88990', 'city': 'Mumbai', 'total_orders': 21, 'total_spend': 11400.00, 'avg_order_value': 542.86, 'recency_days': 27, 'last_order_str': '2026-10-05 13:20', 'segment': 'At Risk (High Value Churn)'},
    {'user_id': 118, 'name': 'Shalini Nair', 'email': 'shalini.nair@gmail.com', 'phone': '+91 98470 66554', 'city': 'Bangalore', 'total_orders': 27, 'total_spend': 14900.00, 'avg_order_value': 551.85, 'recency_days': 2, 'last_order_str': '2026-10-30 20:45', 'segment': 'Champions (VIP)'},
    {'user_id': 119, 'name': 'Amitabh Roy', 'email': 'amitabh.roy@gmail.com', 'phone': '+91 98300 22110', 'city': 'Bangalore', 'total_orders': 14, 'total_spend': 7400.00, 'avg_order_value': 528.57, 'recency_days': 8, 'last_order_str': '2026-10-24 11:30', 'segment': 'Loyal Regulars'},
    {'user_id': 120, 'name': 'Deepak Choudhary', 'email': 'deepak.c@gmail.com', 'phone': '+91 98290 33445', 'city': 'Hyderabad', 'total_orders': 5, 'total_spend': 2650.00, 'avg_order_value': 530.00, 'recency_days': 4, 'last_order_str': '2026-10-28 17:15', 'segment': 'Recent / Promising'},
]


def _get_fallback_rfm_customers() -> List[Dict[str, Any]]:
    """Compute customer RFM segments in Python over existing orders, falling back to rich demo profiles."""
    try:
        orders = get_all_orders_with_user_info()
        if len(orders) >= 5:
            users_map: Dict[int, Dict[str, Any]] = {}
            now = datetime(2026, 11, 1)
            for o in orders:
                uid = o.get('user_id')
                if not uid:
                    continue
                if uid not in users_map:
                    users_map[uid] = {
                        'user_id': uid,
                        'name': str(o.get('full_name') or 'Valued Customer'),
                        'email': str(o.get('user_email') or 'customer@dailydrop.com'),
                        'phone': str(o.get('phone_number') or '+91 98765 00000'),
                        'city': str(o.get('city') or 'Bangalore'),
                        'total_orders': 0,
                        'total_spend': 0.0,
                        'last_order_date': None,
                    }
                u = users_map[uid]
                u['total_orders'] += 1
                u['total_spend'] += float(o.get('total_amount') or 0.0)
                odate = o.get('order_date')
                if isinstance(odate, str):
                    try:
                        dt = datetime.fromisoformat(odate[:19])
                    except Exception:
                        dt = now
                elif isinstance(odate, datetime):
                    dt = odate
                else:
                    dt = now
                if u['last_order_date'] is None or dt > u['last_order_date']:
                    u['last_order_date'] = dt

            if len(users_map) >= 3:
                cust_list = list(users_map.values())
                for c in cust_list:
                    c['total_spend'] = round(c['total_spend'], 2)
                    c['avg_order_value'] = round(c['total_spend'] / c['total_orders'], 2) if c['total_orders'] > 0 else 0.0
                    rec = (now - c['last_order_date']).days if c['last_order_date'] else 99
                    c['recency_days'] = max(0, rec)
                    c['last_order_str'] = c['last_order_date'].strftime('%Y-%m-%d %H:%M') if c['last_order_date'] else 'N/A'
                    if c['recency_days'] >= 15:
                        c['segment'] = 'At Risk (High Value Churn)'
                    elif c['total_spend'] >= 5000:
                        c['segment'] = 'Champions (VIP)'
                    elif c['total_orders'] >= 5:
                        c['segment'] = 'Loyal Regulars'
                    else:
                        c['segment'] = 'Recent / Promising'
                cust_list.sort(key=lambda x: x['total_spend'], reverse=True)
                return cust_list
    except Exception as e:
        logger.debug(f"Fallback customer segmentation: {e}")
    return list(_DEFAULT_CUSTOMER_PROFILES)


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
                            SELECT COALESCE(json_agg(c), '[]'::json) FROM (
                                SELECT COALESCE(p.category, 'Grocery') as category, SUM(oi.subtotal) as cat_revenue
                                FROM order_items oi
                                LEFT JOIN products p ON oi.product_id = p.product_id
                                GROUP BY 1
                            ) c
                        ) AS category_rows;
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

                # Process category totals from SQL aggregate
                for c in (row.get('category_rows') or []):
                    if isinstance(c, dict) and c.get('category'):
                        cat_name = c['category']
                        rev = float(c.get('cat_revenue') or 0.0)
                        category_totals[cat_name] = round(category_totals.get(cat_name, 0.0) + rev, 2)

                # Fallback if order_items has not yet been populated
                if sum(category_totals.values()) == 0.0 and total_orders > 0:
                    cursor.execute("SELECT products_ordered FROM orders LIMIT 200")
                    for cord in cursor.fetchall():
                        try:
                            raw_items = cord['products_ordered'] if isinstance(cord, dict) else cord[0]
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

                city_sla = []
                try:
                    cursor.execute("""
                        SELECT 
                            COALESCE(city, 'Bangalore') as city,
                            COUNT(order_id) as orders,
                            ROUND(AVG(total_amount), 2) as aov,
                            ROUND(AVG(COALESCE(delivery_duration_minutes, 7.2)), 2) as avg_duration,
                            ROUND((SUM(CASE WHEN COALESCE(delivery_duration_minutes, 7.2) <= 10.0 THEN 1.0 ELSE 0.0 END) / COUNT(order_id)) * 100.0, 1) as sla_pct
                        FROM orders
                        WHERE status = 'Delivered'
                        GROUP BY COALESCE(city, 'Bangalore')
                        ORDER BY orders DESC;
                    """)
                    city_sla = [dict(r) for r in cursor.fetchall()]
                except Exception:
                    pass

                rfm_summary = []
                try:
                    cursor.execute("""
                        WITH customer_aggregates AS (
                            SELECT 
                                o.user_id,
                                COUNT(o.order_id) AS total_orders,
                                SUM(o.total_amount) AS total_spend,
                                EXTRACT(DAY FROM ('2026-11-01'::timestamp - MAX(o.order_date)))::integer AS recency_days
                            FROM orders o
                            WHERE o.status = 'Delivered'
                            GROUP BY o.user_id
                        ),
                        rfm_scores AS (
                            SELECT 
                                user_id,
                                NTILE(5) OVER (ORDER BY recency_days DESC) AS r_score,
                                NTILE(5) OVER (ORDER BY total_orders ASC) AS f_score,
                                NTILE(5) OVER (ORDER BY total_spend ASC) AS m_score
                            FROM customer_aggregates
                        )
                        SELECT 
                            CASE 
                                WHEN r_score >= 4 AND f_score >= 4 AND m_score >= 4 THEN 'Champions (VIP)'
                                WHEN r_score >= 3 AND f_score >= 3 THEN 'Loyal Customers'
                                WHEN r_score >= 4 AND f_score <= 2 THEN 'Recent / Promising'
                                WHEN r_score <= 2 AND f_score >= 3 THEN 'At Risk (High Value Churn)'
                                WHEN r_score <= 2 AND f_score <= 2 THEN 'Hibernating / Lost'
                                ELSE 'Needs Attention'
                            END AS segment,
                            COUNT(*) as count
                        FROM rfm_scores
                        GROUP BY 1
                        ORDER BY count DESC;
                    """)
                    rfm_summary = [dict(r) for r in cursor.fetchall()]
                except Exception:
                    pass

                rfm_customers = []
                try:
                    cursor.execute("""
                        WITH customer_aggregates AS (
                            SELECT 
                                o.user_id,
                                MAX(o.full_name) as full_name,
                                MAX(o.phone_number) as phone,
                                MAX(COALESCE(o.city, 'Bangalore')) as city,
                                COUNT(o.order_id) AS total_orders,
                                SUM(o.total_amount) AS total_spend,
                                MAX(o.order_date) as last_order_date,
                                EXTRACT(DAY FROM ('2026-11-01'::timestamp - MAX(o.order_date)))::integer AS recency_days
                            FROM orders o
                            WHERE o.status = 'Delivered'
                            GROUP BY o.user_id
                        ),
                        rfm_scores AS (
                            SELECT 
                                ca.*,
                                NTILE(5) OVER (ORDER BY recency_days DESC) AS r_score,
                                NTILE(5) OVER (ORDER BY total_orders ASC) AS f_score,
                                NTILE(5) OVER (ORDER BY total_spend ASC) AS m_score
                            FROM customer_aggregates ca
                        ),
                        segmented AS (
                            SELECT 
                                s.*,
                                COALESCE(u.email, 'customer@dailydrop.com') as user_email,
                                COALESCE(u.name, s.full_name) as customer_name,
                                CASE 
                                    WHEN r_score >= 4 AND f_score >= 4 AND m_score >= 4 THEN 'Champions (VIP)'
                                    WHEN r_score >= 3 AND f_score >= 3 THEN 'Loyal Regulars'
                                    WHEN r_score >= 4 AND f_score <= 2 THEN 'Recent / Promising'
                                    WHEN r_score <= 2 AND f_score >= 3 THEN 'At Risk (High Value Churn)'
                                    WHEN r_score <= 2 AND f_score <= 2 THEN 'Hibernating / Lost'
                                    ELSE 'Needs Attention'
                                END AS segment
                            FROM rfm_scores s
                            LEFT JOIN users u ON s.user_id = u.id
                        )
                        SELECT 
                            user_id,
                            customer_name as name,
                            user_email as email,
                            phone,
                            city,
                            total_orders,
                            ROUND(total_spend, 2) as total_spend,
                            ROUND(total_spend / total_orders, 2) as avg_order_value,
                            recency_days,
                            TO_CHAR(last_order_date, 'YYYY-MM-DD HH24:MI') as last_order_str,
                            segment
                        FROM segmented
                        ORDER BY total_spend DESC;
                    """)
                    for r in cursor.fetchall():
                        rfm_customers.append({
                            'user_id': int(r['user_id']),
                            'name': str(r['name'] or 'Valued Customer'),
                            'email': str(r['email'] or 'customer@dailydrop.com'),
                            'phone': str(r['phone'] or '+91 98765 00000'),
                            'city': str(r['city'] or 'Bangalore'),
                            'total_orders': int(r['total_orders'] or 0),
                            'total_spend': float(r['total_spend'] or 0.0),
                            'avg_order_value': float(r['avg_order_value'] or 0.0),
                            'recency_days': int(r['recency_days'] or 0),
                            'last_order_str': str(r['last_order_str'] or 'N/A'),
                            'segment': str(r['segment'])
                        })
                except Exception as e:
                    logger.debug(f"SQL rfm_customers error: {e}")

                if not rfm_customers:
                    rfm_customers = _get_fallback_rfm_customers()

                abc_summary = []
                try:
                    cursor.execute("""
                        WITH product_sales AS (
                            SELECT 
                                oi.product_id,
                                SUM(oi.subtotal) AS total_revenue
                            FROM order_items oi
                            JOIN orders o ON oi.order_id = o.order_id
                            WHERE o.status = 'Delivered'
                            GROUP BY oi.product_id
                        ),
                        ranked AS (
                            SELECT 
                                product_id,
                                total_revenue,
                                SUM(total_revenue) OVER () as overall,
                                SUM(total_revenue) OVER (ORDER BY total_revenue DESC ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) as cum
                            FROM product_sales
                        )
                        SELECT 
                            CASE 
                                WHEN (cum * 100.0) / overall <= 80.0 THEN 'Class A (80% GMV)'
                                WHEN (cum * 100.0) / overall <= 95.0 THEN 'Class B (15% GMV)'
                                ELSE 'Class C (5% GMV)'
                            END as abc_class,
                            COUNT(*) as count,
                            ROUND(SUM(total_revenue), 2) as revenue
                        FROM ranked
                        GROUP BY 1;
                    """)
                    abc_summary = [dict(r) for r in cursor.fetchall()]
                except Exception:
                    pass

                market_basket = []
                try:
                    cursor.execute("""
                        WITH item_pairs AS (
                            SELECT 
                                oi1.product_name AS product_a,
                                oi2.product_name AS product_b,
                                COUNT(DISTINCT oi1.order_id) AS pair_orders
                            FROM order_items oi1
                            JOIN order_items oi2 ON oi1.order_id = oi2.order_id AND oi1.product_id < oi2.product_id
                            GROUP BY oi1.product_name, oi2.product_name
                        ),
                        item_counts AS (
                            SELECT product_name, COUNT(DISTINCT order_id) AS item_orders
                            FROM order_items
                            GROUP BY product_name
                        ),
                        total_delivered AS (
                            SELECT COUNT(DISTINCT order_id) AS total_orders FROM orders WHERE status = 'Delivered'
                        )
                        SELECT 
                            p.product_a,
                            p.product_b,
                            p.pair_orders,
                            ROUND((p.pair_orders::numeric * t.total_orders) / (c1.item_orders * c2.item_orders), 2) AS lift
                        FROM item_pairs p
                        CROSS JOIN total_delivered t
                        JOIN item_counts c1 ON p.product_a = c1.product_name
                        JOIN item_counts c2 ON p.product_b = c2.product_name
                        ORDER BY p.pair_orders DESC, lift DESC
                        LIMIT 6;
                    """)
                    for r in cursor.fetchall():
                        market_basket.append({
                            'product_a': str(r['product_a']),
                            'product_b': str(r['product_b']),
                            'pair_orders': int(r['pair_orders']),
                            'lift': float(r['lift']) if r['lift'] is not None else 1.0
                        })
                except Exception:
                    pass

                cohort_matrix = []
                try:
                    cursor.execute("""
                        WITH user_first_order AS (
                            SELECT user_id, DATE_TRUNC('month', MIN(order_date)) AS cohort_month
                            FROM orders
                            WHERE status = 'Delivered'
                            GROUP BY user_id
                        ),
                        user_activities AS (
                            SELECT 
                                o.user_id,
                                ufo.cohort_month,
                                (EXTRACT(YEAR FROM o.order_date) - EXTRACT(YEAR FROM ufo.cohort_month)) * 12 +
                                (EXTRACT(MONTH FROM o.order_date) - EXTRACT(MONTH FROM ufo.cohort_month)) AS month_number
                            FROM orders o
                            JOIN user_first_order ufo ON o.user_id = ufo.user_id
                            WHERE o.status = 'Delivered'
                            GROUP BY o.user_id, ufo.cohort_month, month_number
                        ),
                        cohort_sizes AS (
                            SELECT cohort_month, COUNT(DISTINCT user_id) as total_users
                            FROM user_first_order
                            GROUP BY cohort_month
                        ),
                        cohort_retention AS (
                            SELECT 
                                TO_CHAR(ua.cohort_month, 'YYYY-MM') as cohort,
                                cs.total_users,
                                ua.month_number,
                                COUNT(DISTINCT ua.user_id) as active_users,
                                ROUND((COUNT(DISTINCT ua.user_id)::numeric / cs.total_users) * 100.0, 1) as retention_rate
                            FROM user_activities ua
                            JOIN cohort_sizes cs ON ua.cohort_month = cs.cohort_month
                            GROUP BY ua.cohort_month, cs.total_users, ua.month_number
                            ORDER BY cohort, month_number
                        )
                        SELECT * FROM cohort_retention WHERE cohort >= '2026-05' ORDER BY cohort DESC, month_number ASC;
                    """)
                    cohort_rows = cursor.fetchall()
                    cohort_map = {}
                    for r in cohort_rows:
                        c_name = str(r['cohort'])
                        if c_name not in cohort_map:
                            cohort_map[c_name] = {
                                'cohort': c_name,
                                'total_users': int(r['total_users']),
                                'm0': None, 'm1': None, 'm2': None, 'm3': None, 'm4': None, 'm5': None
                            }
                        m_idx = int(r['month_number'])
                        if 0 <= m_idx <= 5:
                            cohort_map[c_name][f'm{m_idx}'] = float(r['retention_rate'])
                    cohort_matrix = list(cohort_map.values())
                except Exception:
                    pass

                if not market_basket:
                    market_basket = [
                        {'product_a': 'Pepsi Refreshing Soda Can (300 ml)', 'product_b': 'Sprite Clear Lemon-Lime Bottle (750 ml)', 'pair_orders': 17, 'lift': 7.62},
                        {'product_a': 'Coca-Cola Refreshing Soda Can (300 ml)', 'product_b': 'Fanta Orange Soda Bottle (750 ml)', 'pair_orders': 17, 'lift': 6.47},
                        {'product_a': "Cavin's Badam Flavoured Milk (200 ml)", 'product_b': 'Sting Energy Drink Pet Bottle (250 ml)', 'pair_orders': 17, 'lift': 5.82},
                        {'product_a': 'Amul Rose Flavour Sweet Lassi (200 ml)', 'product_b': 'Real Lychee Fruit Lassi (200 ml)', 'pair_orders': 16, 'lift': 7.42},
                        {'product_a': 'Fresh Mango Sweet Lassi (250 ml)', 'product_b': 'Sprite Lemon & Lime Can (300 ml)', 'pair_orders': 16, 'lift': 6.34},
                        {'product_a': "Cavin's Badam Flavoured Milk (200 ml)", 'product_b': 'Pepsi Cola Soft Drink Bottle (750 ml)', 'pair_orders': 15, 'lift': 4.91}
                    ]

                if not cohort_matrix:
                    cohort_matrix = [
                        {'cohort': '2026-10', 'total_users': 44, 'm0': 100.0, 'm1': None, 'm2': None, 'm3': None, 'm4': None, 'm5': None},
                        {'cohort': '2026-09', 'total_users': 27, 'm0': 100.0, 'm1': 81.5, 'm2': None, 'm3': None, 'm4': None, 'm5': None},
                        {'cohort': '2026-08', 'total_users': 24, 'm0': 100.0, 'm1': 83.3, 'm2': 87.5, 'm3': None, 'm4': None, 'm5': None},
                        {'cohort': '2026-07', 'total_users': 26, 'm0': 100.0, 'm1': 76.9, 'm2': 73.1, 'm3': 73.1, 'm4': None, 'm5': None},
                        {'cohort': '2026-06', 'total_users': 24, 'm0': 100.0, 'm1': 95.8, 'm2': 95.8, 'm3': 95.8, 'm4': 91.7, 'm5': None},
                        {'cohort': '2026-05', 'total_users': 27, 'm0': 100.0, 'm1': 66.7, 'm2': 66.7, 'm3': 70.4, 'm4': 66.7, 'm5': 59.3}
                    ]

                at_risk_list = [c for c in rfm_customers if 'At Risk' in c.get('segment', '')]
                vip_list = [c for c in rfm_customers if 'Champions' in c.get('segment', '')]
                loyal_list = [c for c in rfm_customers if 'Loyal' in c.get('segment', '')]
                at_risk_spend_val = sum(float(c.get('total_spend', 0.0)) for c in at_risk_list)
                vip_spend_val = sum(float(c.get('total_spend', 0.0)) for c in vip_list)

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
                    'hourly': hour_counts,
                    'city_sla': city_sla,
                    'rfm_summary': rfm_summary,
                    'rfm_customers': rfm_customers,
                    'at_risk_customers': at_risk_list,
                    'vip_customers': vip_list,
                    'loyal_customers': loyal_list,
                    'at_risk_count': len(at_risk_list),
                    'vip_count': len(vip_list),
                    'at_risk_spend': at_risk_spend_val,
                    'vip_spend': vip_spend_val,
                    'abc_summary': abc_summary,
                    'cohort_matrix': cohort_matrix,
                    'market_basket': market_basket
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

                    fallback_cust = _get_fallback_rfm_customers()
                    at_risk_fb = [c for c in fallback_cust if 'At Risk' in c.get('segment', '')]
                    vip_fb = [c for c in fallback_cust if 'Champions' in c.get('segment', '')]
                    loyal_fb = [c for c in fallback_cust if 'Loyal' in c.get('segment', '')]

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
                        'hourly': hour_counts,
                        'city_sla': [],
                        'rfm_summary': [],
                        'rfm_customers': fallback_cust,
                        'at_risk_customers': at_risk_fb,
                        'vip_customers': vip_fb,
                        'loyal_customers': loyal_fb,
                        'at_risk_count': len(at_risk_fb),
                        'vip_count': len(vip_fb),
                        'at_risk_spend': sum(float(c.get('total_spend', 0.0)) for c in at_risk_fb),
                        'vip_spend': sum(float(c.get('total_spend', 0.0)) for c in vip_fb),
                        'abc_summary': [],
                        'cohort_matrix': [
                            {'cohort': '2026-10', 'total_users': 44, 'm0': 100.0, 'm1': None, 'm2': None, 'm3': None, 'm4': None, 'm5': None},
                            {'cohort': '2026-09', 'total_users': 27, 'm0': 100.0, 'm1': 81.5, 'm2': None, 'm3': None, 'm4': None, 'm5': None},
                            {'cohort': '2026-08', 'total_users': 24, 'm0': 100.0, 'm1': 83.3, 'm2': 87.5, 'm3': None, 'm4': None, 'm5': None},
                            {'cohort': '2026-07', 'total_users': 26, 'm0': 100.0, 'm1': 76.9, 'm2': 73.1, 'm3': 73.1, 'm4': None, 'm5': None},
                            {'cohort': '2026-06', 'total_users': 24, 'm0': 100.0, 'm1': 95.8, 'm2': 95.8, 'm3': 95.8, 'm4': 91.7, 'm5': None},
                            {'cohort': '2026-05', 'total_users': 27, 'm0': 100.0, 'm1': 66.7, 'm2': 66.7, 'm3': 70.4, 'm4': 66.7, 'm5': 59.3}
                        ],
                        'market_basket': [
                            {'product_a': 'Pepsi Refreshing Soda Can (300 ml)', 'product_b': 'Sprite Clear Lemon-Lime Bottle (750 ml)', 'pair_orders': 17, 'lift': 7.62},
                            {'product_a': 'Coca-Cola Refreshing Soda Can (300 ml)', 'product_b': 'Fanta Orange Soda Bottle (750 ml)', 'pair_orders': 17, 'lift': 6.47},
                            {'product_a': "Cavin's Badam Flavoured Milk (200 ml)", 'product_b': 'Sting Energy Drink Pet Bottle (250 ml)', 'pair_orders': 17, 'lift': 5.82},
                            {'product_a': 'Amul Rose Flavour Sweet Lassi (200 ml)', 'product_b': 'Real Lychee Fruit Lassi (200 ml)', 'pair_orders': 16, 'lift': 7.42},
                            {'product_a': 'Fresh Mango Sweet Lassi (250 ml)', 'product_b': 'Sprite Lemon & Lime Can (300 ml)', 'pair_orders': 16, 'lift': 6.34},
                            {'product_a': "Cavin's Badam Flavoured Milk (200 ml)", 'product_b': 'Pepsi Cola Soft Drink Bottle (750 ml)', 'pair_orders': 15, 'lift': 4.91}
                        ]
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


def get_customer_audiences(days: int = 30) -> List[Dict[str, Any]]:
    """Retrieve detailed customer audience profiles scored by RFM segmentation."""
    analytics = get_unified_analytics(days=days)
    return analytics.get('rfm_customers', [])



def update_product_price(product_id: int, price: float) -> bool:
    """Update a product's price."""
    updated = False
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute('UPDATE products SET price = %s WHERE product_id = %s', (price, product_id))
                updated = cursor.rowcount > 0

        if updated:
            clear_product_cache(product_id)
        return updated
    except Exception as e:
        logger.error(f"Error updating product price: {e}")
        raise DatabaseError(f"Failed to update product price: {e}") from e


def update_product_stock(product_id: int, stock: int) -> bool:
    """Update a product's stock quantity."""
    updated = False
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute('UPDATE products SET stock = %s WHERE product_id = %s', (stock, product_id))
                updated = cursor.rowcount > 0

        if updated:
            clear_product_cache(product_id)
            try:
                from services.redis_service import RedisService
                RedisService.set_stock(product_id, stock)
            except Exception:
                pass
        return updated
    except Exception as e:
        logger.error(f"Error updating product stock: {e}")
        raise DatabaseError(f"Failed to update product stock: {e}") from e


def update_product(product_id: int, name: Optional[str] = None, price: Optional[float] = None,
                   category: Optional[str] = None, subcategory: Optional[str] = None,
                   image_path: Optional[str] = None, description: Optional[str] = None,
                   stock: Optional[int] = None) -> bool:
    """Update all or selected fields of an existing product in the catalog."""
    updates = []
    params = []
    if name is not None and name.strip():
        updates.append("name = %s")
        params.append(name.strip())
    if price is not None:
        updates.append("price = %s")
        params.append(float(price))
    if category is not None and category.strip():
        updates.append("category = %s")
        params.append(normalize_category(category))
    if subcategory is not None:
        updates.append("subcategory = %s")
        params.append(subcategory.strip())
    if image_path is not None and image_path.strip():
        updates.append("image_path = %s")
        params.append(image_path.strip())
    if description is not None:
        updates.append("description = %s")
        params.append(description.strip())
    if stock is not None:
        updates.append("stock = %s")
        params.append(int(stock))

    if not updates:
        return True

    params.append(product_id)
    query = f"UPDATE products SET {', '.join(updates)} WHERE product_id = %s"
    updated = False
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, tuple(params))
                updated = cursor.rowcount > 0

        if updated:
            clear_product_cache(product_id)
            if stock is not None:
                try:
                    from services.redis_service import RedisService
                    RedisService.set_stock(product_id, int(stock))
                except Exception:
                    pass
        return updated
    except Exception as e:
        logger.error(f"Error updating product #{product_id}: {e}")
        raise DatabaseError(f"Failed to update product: {e}") from e


def add_product(name: str, price: float, category: str, subcategory: str = '',
                image_path: str = '/static/product-placeholder.svg', description: str = '', stock: int = 50) -> int:
    """Add a new product to the database catalog."""
    category = normalize_category(category)
    pid = None
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute('''
                    INSERT INTO products (name, price, category, subcategory, image_path, description, stock)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING product_id
                ''', (name, price, category, subcategory, image_path, description, stock))
                row = cursor.fetchone()
                if row:
                    pid = row['product_id']

        if pid:
            clear_product_cache(pid)
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
    deleted = False
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute('DELETE FROM products WHERE product_id = %s', (product_id,))
                deleted = cursor.rowcount > 0

        if deleted:
            clear_product_cache(product_id)
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
                except Exception as query_err:
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

