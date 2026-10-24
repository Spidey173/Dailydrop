"""
Flask extensions initialized independently to prevent circular imports.
"""
import os
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

csrf = CSRFProtect()


def _get_limiter_storage() -> str:
    """Determine the optimal storage backend for distributed or local rate limiting."""
    custom_uri = os.getenv("RATELIMIT_STORAGE_URI")
    if custom_uri:
        return custom_uri

    redis_enabled = os.getenv("REDIS_ENABLED", "true").lower() in ("true", "1", "yes")
    redis_url = os.getenv("REDIS_URL")
    flask_env = os.getenv("FLASK_ENV", "development").lower()

    # Use Redis in non-testing environments if Redis is enabled and configured
    if redis_enabled and redis_url and flask_env != "testing":
        return redis_url

    return "memory://"


limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri=_get_limiter_storage(),
    in_memory_fallback_enabled=True,
    swallow_errors=True
)

