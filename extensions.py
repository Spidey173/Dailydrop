"""
Flask extensions initialized independently to prevent circular imports.
"""
import os
import re
import logging
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

logger = logging.getLogger(__name__)

csrf = CSRFProtect()


def _sanitize_url(raw_url: str) -> str:
    """Extract clean URL from possible CLI commands."""
    if not raw_url:
        return ""
    url = raw_url.strip().strip('\'\"')
    if 'redis-cli' in url:
        has_tls = '--tls' in url
        match = re.search(r'-u\s+([^\s\'\"]+)', url)
        if match:
            url = match.group(1).strip('\'\"')
        else:
            match = re.search(r'(rediss?://[^\s\'\"]+)', url)
            if match:
                url = match.group(1).strip('\'\"')
        if has_tls and url.startswith('redis://'):
            url = 'rediss://' + url[8:]
    return url


def _get_limiter_storage() -> str:
    """Determine the optimal storage backend for distributed or local rate limiting."""
    try:
        custom_uri = os.getenv("RATELIMIT_STORAGE_URI")
        if custom_uri:
            clean = _sanitize_url(custom_uri)
            if clean.startswith(('redis://', 'rediss://', 'memory://')):
                return clean

        redis_enabled = os.getenv("REDIS_ENABLED", "true").lower() in ("true", "1", "yes")
        redis_url = os.getenv("REDIS_URL")
        flask_env = os.getenv("FLASK_ENV", "development").lower()

        # Use Redis in non-testing environments if Redis is enabled and configured
        if redis_enabled and redis_url and flask_env != "testing":
            clean = _sanitize_url(redis_url)
            if clean.startswith(('redis://', 'rediss://')):
                return clean
    except Exception as e:
        logger.warning(f"Error resolving limiter storage URI ({e}), defaulting to memory://")

    return "memory://"


limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri=_get_limiter_storage(),
    in_memory_fallback_enabled=True,
    swallow_errors=True
)


