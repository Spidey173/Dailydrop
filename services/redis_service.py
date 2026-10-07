"""
Redis Service Module for Daily Drop.

Provides:
1. Resilient Redis connection pooling and health checking.
2. Atomic Lua scripts for sub-millisecond flash-sale stock management.
3. Read-through caching utilities with automatic JSON serialization.
4. Graceful fallbacks when Redis is offline or unavailable.
"""

import json
import logging
import time
from typing import Optional, Any, Tuple, Dict, List
import redis
from config import Config

logger = logging.getLogger(__name__)

# Atomic stock decrement Lua script:
# Returns:
#   1  -> Decrement successful
#   0  -> Insufficient stock (out of stock)
#  -1  -> Key does not exist in Redis (requires hydration from DB)
_LUA_DECREMENT_STOCK = """
local current = redis.call('get', KEYS[1])
if not current then
    return -1
end
local stock = tonumber(current)
local qty = tonumber(ARGV[1])
if stock >= qty then
    redis.call('decrby', KEYS[1], qty)
    return 1
else
    return 0
end
"""

# Atomic stock rollback / release Lua script:
_LUA_ROLLBACK_STOCK = """
local exists = redis.call('exists', KEYS[1])
if exists == 1 then
    redis.call('incrby', KEYS[1], ARGV[1])
    return 1
end
return 0
"""


class RedisService:
    """Manages Redis connection, cache-aside operations, and flash-sale atomic locks."""

    _pool: Optional[redis.ConnectionPool] = None
    _client: Optional[redis.Redis] = None
    _decr_script = None
    _rollback_script = None
    _last_failure_time: float = 0.0
    _CIRCUIT_COOLDOWN_SECONDS: float = 15.0  # Cooldown before retrying a down Redis server

    _raw_pool: Optional[redis.ConnectionPool] = None
    _raw_client: Optional[redis.Redis] = None

    @classmethod
    def get_raw_client(cls) -> Optional[redis.Redis]:
        """
        Get Redis client without decode_responses=True.
        Required by queueing libraries (RQ/Celery) that handle binary payloads.
        """
        if not getattr(Config, 'REDIS_ENABLED', True):
            return None

        now = time.time()
        if cls._last_failure_time and (now - cls._last_failure_time < cls._CIRCUIT_COOLDOWN_SECONDS):
            return None

        if cls._raw_client is not None:
            return cls._raw_client

        try:
            redis_url = getattr(Config, 'REDIS_URL', 'redis://127.0.0.1:6379/0')
            socket_timeout = getattr(Config, 'REDIS_SOCKET_TIMEOUT', 2.0)
            cls._raw_pool = redis.ConnectionPool.from_url(
                redis_url,
                socket_timeout=socket_timeout,
                socket_connect_timeout=socket_timeout,
                max_connections=20,
                decode_responses=False
            )
            cls._raw_client = redis.Redis(connection_pool=cls._raw_pool)
            cls._raw_client.ping()
            return cls._raw_client
        except Exception as e:
            cls._last_failure_time = time.time()
            cls._raw_client = None
            cls._raw_pool = None
            logger.warning(f"Raw Redis client unavailable: {e}")
            return None

    @classmethod
    def get_client(cls) -> Optional[redis.Redis]:
        """
        Get or initialize the shared Redis client with connection pooling.
        Returns None gracefully if Redis is disabled or unreachable.
        """
        if not getattr(Config, 'REDIS_ENABLED', True):
            return None

        # Circuit-breaker cooldown if recently failed
        now = time.time()
        if cls._last_failure_time and (now - cls._last_failure_time < cls._CIRCUIT_COOLDOWN_SECONDS):
            return None

        if cls._client is not None:
            return cls._client

        try:
            redis_url = getattr(Config, 'REDIS_URL', 'redis://127.0.0.1:6379/0')
            socket_timeout = getattr(Config, 'REDIS_SOCKET_TIMEOUT', 2.0)
            
            cls._pool = redis.ConnectionPool.from_url(
                redis_url,
                socket_timeout=socket_timeout,
                socket_connect_timeout=socket_timeout,
                max_connections=20,
                decode_responses=True
            )
            client = redis.Redis(connection_pool=cls._pool)
            client.ping()  # Health check
            
            # Register Lua scripts
            cls._decr_script = client.register_script(_LUA_DECREMENT_STOCK)
            cls._rollback_script = client.register_script(_LUA_ROLLBACK_STOCK)
            cls._client = client
            cls._last_failure_time = 0.0
            logger.info("Connected to Redis successfully for caching & distributed locking.")
            return cls._client
        except Exception as e:
            cls._last_failure_time = time.time()
            cls._client = None
            cls._pool = None
            logger.warning(f"Redis unavailable ({e}). Gracefully falling back to relational database tier.")
            return None

    @classmethod
    def is_available(cls) -> bool:
        """Check if Redis connection is active."""
        client = cls.get_client()
        if client is None:
            return False
        try:
            return bool(client.ping())
        except Exception:
            cls._last_failure_time = time.time()
            cls._client = None
            return False

    # =========================================================================
    # 1. Flash-Sale Concurrency: Distributed Redis Stock Lua Scripts
    # =========================================================================

    @classmethod
    def stock_key(cls, product_id: int) -> str:
        return f"stock:product:{product_id}"

    @classmethod
    def set_stock(cls, product_id: int, stock: int, ttl: int = 86400) -> bool:
        """Set authoritative product stock in Redis."""
        client = cls.get_client()
        if not client:
            return False
        try:
            client.set(cls.stock_key(product_id), int(stock), ex=ttl)
            return True
        except Exception as e:
            logger.warning(f"Redis set_stock failed for product {product_id}: {e}")
            return False

    @classmethod
    def get_stock(cls, product_id: int) -> Optional[int]:
        """Fetch cached stock count from Redis."""
        client = cls.get_client()
        if not client:
            return None
        try:
            val = client.get(cls.stock_key(product_id))
            return int(val) if val is not None else None
        except Exception as e:
            logger.warning(f"Redis get_stock failed for product {product_id}: {e}")
            return None

    @classmethod
    def atomic_decrement_stock(
        cls,
        product_id: int,
        quantity: int,
        fallback_db_stock: Optional[int] = None
    ) -> Tuple[bool, str, int]:
        """
        Execute sub-millisecond atomic inventory decrement via Lua script.

        Returns:
            Tuple[bool, str, int]:
            - success: True if decremented, False otherwise
            - message: explanation string
            - remaining_stock: approximate remaining stock or -1 if unknown
        """
        client = cls.get_client()
        if not client or cls._decr_script is None:
            return True, "Redis bypassed", -1

        key = cls.stock_key(product_id)
        try:
            result = cls._decr_script(keys=[key], args=[quantity])
            
            # -1: Key does not exist in Redis yet
            if result == -1:
                if fallback_db_stock is not None:
                    # Hydrate key into Redis and retry decrement
                    client.set(key, int(fallback_db_stock), ex=86400)
                    result = cls._decr_script(keys=[key], args=[quantity])
                else:
                    return True, "Cache miss; deferred to DB", -1

            if result == 1:
                current = client.get(key)
                rem = int(current) if current is not None else 0
                return True, "Stock decremented successfully", rem
            else:
                current = client.get(key)
                rem = int(current) if current is not None else 0
                return False, f"Insufficient stock. Only {rem} left.", rem
        except Exception as e:
            logger.warning(f"Redis atomic_decrement_stock error for product {product_id}: {e}")
            return True, "Redis error; fell back to DB lock", -1

    @classmethod
    def atomic_rollback_stock(cls, product_id: int, quantity: int) -> bool:
        """Atomically restore / release stock on failed transactions or order cancellation."""
        client = cls.get_client()
        if not client or cls._rollback_script is None:
            return False
        key = cls.stock_key(product_id)
        try:
            cls._rollback_script(keys=[key], args=[quantity])
            return True
        except Exception as e:
            logger.warning(f"Redis rollback stock error for product {product_id}: {e}")
            return False

    # =========================================================================
    # 2. Read-Through / Cache-Aside Catalog Helpers
    # =========================================================================

    @classmethod
    def get_json(cls, key: str) -> Optional[Any]:
        """Retrieve and deserialize a JSON object from Redis cache."""
        client = cls.get_client()
        if not client:
            return None
        try:
            val = client.get(key)
            if val:
                return json.loads(val)
            return None
        except Exception as e:
            logger.debug(f"Redis get_json miss or error for {key}: {e}")
            return None

    @classmethod
    def set_json(cls, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Serialize and cache an object to Redis with expiration TTL."""
        client = cls.get_client()
        if not client:
            return False
        if ttl is None:
            ttl = getattr(Config, 'CACHE_CATALOG_TTL', 600)
        try:
            payload = json.dumps(value, default=str)
            client.set(key, payload, ex=ttl)
            return True
        except Exception as e:
            logger.warning(f"Redis set_json failed for {key}: {e}")
            return False

    @classmethod
    def delete(cls, *keys: str) -> bool:
        """Delete specific keys from Redis."""
        client = cls.get_client()
        if not client or not keys:
            return False
        try:
            client.delete(*keys)
            return True
        except Exception as e:
            logger.warning(f"Redis delete failed for keys {keys}: {e}")
            return False

    @classmethod
    def invalidate_catalog(cls) -> None:
        """Invalidate all catalog-related cached items."""
        client = cls.get_client()
        if not client:
            return
        try:
            # Delete direct master catalog keys
            client.delete("catalog:all_products", "catalog:categories")
            # Invalidate category and product wildcard keys
            for pattern in ["catalog:category:*", "catalog:product:*"]:
                cursor = 0
                while True:
                    cursor, keys = client.scan(cursor=cursor, match=pattern, count=100)
                    if keys:
                        client.delete(*keys)
                    if cursor == 0:
                        break
        except Exception as e:
            logger.warning(f"Error invalidating catalog in Redis: {e}")
