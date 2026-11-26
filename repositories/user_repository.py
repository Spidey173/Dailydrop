"""
User Data Repository.
Handles user persistence, identity lookups, and in-memory session caching.
"""
import time
import logging
from typing import Any, Dict, Optional, Tuple
from psycopg2.extras import RealDictCursor
from core.database import get_db_connection, DatabaseError

logger = logging.getLogger("dailydrop.repositories.user")

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
