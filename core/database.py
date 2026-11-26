"""
Database module for connection pooling and transaction lifecycle.
Provides connection pool management and transaction context managers for Neon PostgreSQL.
Domain queries are modularized in the repositories/ package.
"""

import os
import logging
from typing import Optional
from contextlib import contextmanager
from psycopg2 import pool
from core.config import Config

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
    Validate database connection pool health and warm runtime caches.
    Schema migrations are managed strictly through migrations.runner.
    """
    global _IS_DB_INITIALIZED
    if _IS_DB_INITIALIZED:
        return

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1")
    except Exception as e:
        logger.error(f"Database connection pool check failed: {e}")
        raise DatabaseError(f"Database connection pool check failed: {e}") from e

    # Pre-warm runtime product and user cache
    try:
        from repositories.product_repository import get_all_products
        from repositories.user_repository import get_user_by_email
        from repositories.analytics_repository import get_unified_analytics
        get_all_products()
        get_user_by_email('admin_dailydrop@gmail.com')
        get_user_by_email('demo_dailydrop@gmail.com')
        if not os.getenv('VERCEL'):
            get_unified_analytics(days=30)
    except Exception as e:
        logger.warning(f"Could not pre-warm runtime cache: {e}")

    _IS_DB_INITIALIZED = True
    logger.info("Database connection and runtime cache verified.")
