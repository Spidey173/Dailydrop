"""
Pytest configuration with ephemeral PostgreSQL + Redis via Testcontainers.
Runs every test against real Postgres 16 and Redis 7 for 100% dialect fidelity.
Requires Docker to be running.
"""
import sys
import os
import json
import logging
from unittest.mock import MagicMock

import pytest
from psycopg2 import pool

from testcontainers.community.postgres import PostgresContainer
from testcontainers.community.redis import RedisContainer

# Add root project directory to sys.path
ROOT_DIR = os.path.abspath(os.path.dirname(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

logger = logging.getLogger(__name__)


# =============================================================================
# Session-scoped Testcontainers: Postgres + Redis
# =============================================================================

@pytest.fixture(scope="session")
def _postgres_container():
    """Start a Postgres 16 container once per test session."""
    container = PostgresContainer(
        image="postgres:16-alpine",
        username="test_user",
        password="test_password",
        dbname="dailydrop_test",
    )
    container.start()
    yield container
    container.stop()


@pytest.fixture(scope="session")
def _redis_container():
    """Start a Redis 7 container once per test session."""
    container = RedisContainer(image="redis:7-alpine")
    container.start()
    yield container
    container.stop()


@pytest.fixture(scope="session", autouse=True)
def _setup_test_infrastructure(_postgres_container, _redis_container):
    """
    Session-level autouse fixture:
    1. Points database module at the Postgres testcontainer via a real ThreadedConnectionPool.
    2. Runs all migrations via migrations.runner (single source of truth for schema).
    3. Seeds users and products via seed.py.
    4. Points RedisService at the Redis testcontainer.
    5. Mocks TaskService.get_queue for offline task dispatch.
    """
    pg = _postgres_container
    redis_ctr = _redis_container

    # Build DSN for psycopg2
    pg_url = pg.get_connection_url()
    # testcontainers returns a SQLAlchemy-style URL; convert to psycopg2 DSN
    # e.g. postgresql+psycopg2://user:pass@host:port/db -> postgresql://user:pass@host:port/db
    dsn = pg_url.replace("postgresql+psycopg2://", "postgresql://")

    # Set env vars so config.py and other modules pick them up
    os.environ["DATABASE_URL"] = dsn
    os.environ["FLASK_ENV"] = "testing"
    os.environ["SECRET_KEY"] = "test-mock-secret-key-32bytes-secure-pytest"

    # Redis URL
    redis_host = redis_ctr.get_container_host_ip()
    redis_port = redis_ctr.get_exposed_port(6379)
    redis_url = f"redis://{redis_host}:{redis_port}/0"
    os.environ["REDIS_URL"] = redis_url
    os.environ["REDIS_ENABLED"] = "true"

    # --- Initialize database module with real Postgres pool ---
    import database
    # Close any existing pool
    if database._db_pool and not database._db_pool.closed:
        try:
            database._db_pool.closeall()
        except Exception:
            pass

    test_pool = pool.ThreadedConnectionPool(
        minconn=2,
        maxconn=15,
        dsn=dsn,
    )
    database._db_pool = test_pool
    database._IS_DB_INITIALIZED = True
    database.get_pool = lambda: test_pool

    # --- Run all migrations (single source of truth for schema) ---
    from migrations.runner import run_migrations
    count, versions = run_migrations()
    logger.info(f"Migrations applied: {count} ({versions})")

    # --- Seed users and products ---
    from seed import seed_database
    seed_database()

    # Seed extra test-specific products
    _seed_test_products()

    # --- Configure RedisService to use real Redis container ---
    import redis as redis_lib
    from services.redis_service import RedisService, _LUA_DECREMENT_STOCK, _LUA_ROLLBACK_STOCK

    redis_pool = redis_lib.ConnectionPool.from_url(
        redis_url, decode_responses=True, max_connections=20
    )
    redis_client = redis_lib.Redis(connection_pool=redis_pool)
    redis_client.ping()

    raw_pool = redis_lib.ConnectionPool.from_url(
        redis_url, decode_responses=False, max_connections=20
    )
    raw_client = redis_lib.Redis(connection_pool=raw_pool)

    # Save original methods so tests can access them (e.g. test_redis_service_unmocked_methods)
    RedisService._real_get_client = RedisService.get_client
    RedisService._real_get_raw_client = RedisService.get_raw_client

    RedisService._pool = redis_pool
    RedisService._client = redis_client
    RedisService._raw_pool = raw_pool
    RedisService._raw_client = raw_client
    RedisService._decr_script = redis_client.register_script(_LUA_DECREMENT_STOCK)
    RedisService._rollback_script = redis_client.register_script(_LUA_ROLLBACK_STOCK)
    RedisService._last_failure_time = 0.0
    RedisService.get_client = classmethod(lambda cls: redis_client)
    RedisService.get_raw_client = classmethod(lambda cls: raw_client)
    RedisService.is_available = classmethod(lambda cls: True)

    # --- Mock TaskService queue (no real RQ worker needed) ---
    from services.task_service import TaskService
    mock_job = MagicMock()
    mock_job.id = "mock_job_test_7777"
    mock_rq_queue = MagicMock()
    mock_rq_queue.enqueue.return_value = mock_job
    TaskService.get_queue = classmethod(lambda cls: mock_rq_queue)

    # Pre-warm caches
    try:
        from repositories.product_repository import clear_product_cache, get_all_products
        from repositories.user_repository import clear_user_cache, get_user_by_email
        from repositories.analytics_repository import clear_analytics_cache
        clear_product_cache()
        clear_user_cache()
        clear_analytics_cache()
        get_all_products()
        get_user_by_email('admin_dailydrop@gmail.com')
        get_user_by_email('demo_dailydrop@gmail.com')
    except Exception as e:
        logger.warning(f"Warning pre-warming cache: {e}")

    yield

    # Teardown: close pools
    try:
        test_pool.closeall()
    except Exception:
        pass
    try:
        redis_client.close()
    except Exception:
        pass


def _seed_test_products():
    """Seed extra products referenced by integration tests."""
    from database import get_db_connection
    test_products = [
        ('Organic Tomatoes', 3.99, 'Vegetables', 'Fresh', 50, '/static/fruits-vegetables/tomato.jpg'),
        ('Whole Milk', 4.50, 'Dairy', 'Milk', 50, '/static/dairy-breakfast/milk.jpg'),
        ('Apple', 1.50, 'Fruits', 'Fresh', 50, '/static/fruits-vegetables/apples.jpeg'),
        ('Organic Almonds 500g', 12.50, 'Grocery', 'Dry Fruits', 50, '/static/dairy-breakfast/nut-butter.jpeg'),
        ('Fresh Avocados 2pk', 6.00, 'Fruits', 'Fresh', 50, '/static/fruits-vegetables/cucumber.jpeg'),
        ('Basmati Rice 5kg', 450.00, 'Grocery', 'Rice', 50, '/static/grocery/jasmine-rice.jpg'),
        ('Olive Oil 1L', 600.00, 'Grocery', 'Oils', 50, '/static/grocery/fortune-sunlite-oil.jpeg'),
        ('Organic Apples 1kg', 120.00, 'Fruits', 'Apples', 50, '/static/fruits-vegetables/green-apple.jpeg'),
        ('Tea', 50.00, 'Beverages', 'Tea', 50, '/static/dairy-breakfast/red-label.jpg'),
        ('Brown Bread', 40.00, 'Bakery', 'Bread', 50, '/static/dairy-breakfast/bread.jpg'),
        ('Tamper Proof Oil', 400.00, 'Grocery', 'Oils', 50, '/static/grocery/fortune-sunlite-oil.jpeg'),
    ]
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                for p_name, p_price, p_cat, p_sub, p_stk, p_img in test_products:
                    cursor.execute(
                        """
                        INSERT INTO products (name, price, category, subcategory, image_path, description, stock)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT DO NOTHING
                        """,
                        (p_name, p_price, p_cat, p_sub, p_img, 'Test catalog product', p_stk)
                    )
    except Exception as e:
        logger.warning(f"Warning seeding test products: {e}")


# =============================================================================
# Per-test isolation: truncate all tables + flush Redis
# =============================================================================

# Tables in dependency-safe truncation order (children before parents)
_ALL_TABLES = [
    "outbox_events",
    "wishlist",
    "order_items",
    "pending_orders",
    "orders",
    "contact_messages",
    "products",
    "users",
]


@pytest.fixture(autouse=True)
def _isolate_test():
    """
    Before each test: truncate all data tables and re-seed.
    Uses TRUNCATE ... RESTART IDENTITY CASCADE for speed and correctness.
    Redis is flushed to clear stock cache and idempotency keys.
    """
    from database import get_db_connection
    from services.redis_service import RedisService

    # Truncate all data tables (not schema_migrations)
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "TRUNCATE TABLE {} RESTART IDENTITY CASCADE".format(
                    ", ".join(_ALL_TABLES)
                )
            )

    # Flush Redis
    client = RedisService.get_client()
    if client:
        try:
            client.flushdb()
        except Exception:
            pass

    # Re-seed minimal fixtures
    _reseed_fixtures()

    # Clear caches so tests start fresh
    try:
        from repositories.product_repository import clear_product_cache
        from repositories.user_repository import clear_user_cache
        from repositories.analytics_repository import clear_analytics_cache
        clear_product_cache()
        clear_user_cache()
        clear_analytics_cache()
    except Exception:
        pass

    yield


def _reseed_fixtures():
    """Re-seed users and products for each test."""
    from database import get_db_connection
    from werkzeug.security import generate_password_hash

    admin_pass = generate_password_hash('Dailydrop@173')
    demo_pass = generate_password_hash('Demouser@123')

    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            # Users
            cursor.execute(
                "INSERT INTO users (name, email, password, role) VALUES (%s, %s, %s, %s) ON CONFLICT (email) DO NOTHING",
                ('Admin User', 'admin_dailydrop@gmail.com', admin_pass, 'admin')
            )
            cursor.execute(
                "INSERT INTO users (name, email, password, role) VALUES (%s, %s, %s, %s) ON CONFLICT (email) DO NOTHING",
                ('Demo Customer', 'demo_dailydrop@gmail.com', demo_pass, 'customer')
            )

    # Seed products from seed file + test-specific products
    _seed_products_from_file()
    _seed_test_products()


def _seed_products_from_file():
    """Seed catalog products from seeds/products.json."""
    from database import get_db_connection
    json_seed = os.path.join(ROOT_DIR, 'seeds', 'products.json')
    js_file = os.path.join(ROOT_DIR, 'static', 'js', 'products.js')
    seed_file = json_seed if os.path.exists(json_seed) else js_file
    if not os.path.exists(seed_file):
        return
    try:
        with open(seed_file, 'r', encoding='utf-8') as f:
            c = f.read()
        if seed_file.endswith('.json'):
            raw_prods = json.loads(c)
        else:
            start = c.find('[')
            end = c.rfind(']') + 1
            raw_prods = json.loads(c[start:end]) if (start != -1 and end != -1) else []

        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                for pid, p in enumerate(raw_prods, start=1):
                    unique_stock = 30 + ((pid * 7) % 65)
                    cursor.execute(
                        """
                        INSERT INTO products (product_id, name, price, category, subcategory, image_path, description, stock)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (product_id) DO NOTHING
                        """,
                        (
                            pid,
                            p.get('title', 'Product'),
                            float(p.get('price', 0)),
                            p.get('category', 'Grocery'),
                            p.get('subcategory', ''),
                            p.get('image', '/static/product-placeholder.svg'),
                            p.get('description', ''),
                            unique_stock
                        )
                    )
                # Reset sequence to max product_id
                cursor.execute(
                    "SELECT setval(pg_get_serial_sequence('products', 'product_id'), COALESCE(MAX(product_id), 1)) FROM products"
                )
    except Exception as e:
        logger.warning(f"Warning seeding catalog products: {e}")


@pytest.fixture(autouse=True)
def check_db_availability():
    """DB availability check: Testcontainer is always available."""
    return
