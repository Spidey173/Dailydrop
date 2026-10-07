import time
from datetime import datetime
from typing import List, Dict, Any, Tuple, Optional
import logging
from psycopg2.extras import RealDictCursor
from database import get_db_connection, DatabaseError

logger = logging.getLogger(__name__)

_WISHLIST_CACHE_TTL = 300.0
_WISHLIST_IDS_CACHE: Dict[int, Tuple[float, List[int]]] = {}
_WISHLIST_ITEMS_CACHE: Dict[int, Tuple[float, List[Dict[str, Any]]]] = {}


def clear_wishlist_cache(user_id: Optional[int] = None) -> None:
    """Clear in-memory cache for user's wishlist."""
    if user_id:
        _WISHLIST_IDS_CACHE.pop(user_id, None)
        _WISHLIST_ITEMS_CACHE.pop(user_id, None)
    else:
        _WISHLIST_IDS_CACHE.clear()
        _WISHLIST_ITEMS_CACHE.clear()


class WishlistService:
    """Service providing wishlist management operations."""

    @staticmethod
    def get_wishlist_count(user_id: int) -> int:
        """Get total number of wishlisted items for a user."""
        now = time.time()
        if user_id in _WISHLIST_IDS_CACHE:
            cached_time, ids = _WISHLIST_IDS_CACHE[user_id]
            if now - cached_time < _WISHLIST_CACHE_TTL:
                return len(ids)

        try:
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT COUNT(*) FROM wishlist WHERE user_id = %s", (user_id,))
                    row = cursor.fetchone()
                    return row[0] if row else 0
        except DatabaseError as e:
            logger.error(f"Error fetching wishlist count for user #{user_id}: {e}")
            return 0

    @staticmethod
    def get_user_wishlist_ids(user_id: int) -> List[int]:
        """Get list of product IDs in user's wishlist with instant in-memory caching."""
        now = time.time()
        if user_id in _WISHLIST_IDS_CACHE:
            cached_time, ids = _WISHLIST_IDS_CACHE[user_id]
            if now - cached_time < _WISHLIST_CACHE_TTL:
                return ids

        try:
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT product_id FROM wishlist WHERE user_id = %s ORDER BY created_at DESC", (user_id,))
                    rows = cursor.fetchall()
                    ids = [r[0] for r in rows]
                    _WISHLIST_IDS_CACHE[user_id] = (now, ids)
                    return ids
        except DatabaseError as e:
            logger.error(f"Error fetching wishlist IDs for user #{user_id}: {e}")
            if user_id in _WISHLIST_IDS_CACHE:
                return _WISHLIST_IDS_CACHE[user_id][1]
            return []


    @staticmethod
    def get_user_wishlist(user_id: int) -> List[Dict[str, Any]]:
        """Get full product details for all wishlisted items of a user."""
        try:
            with get_db_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute('''
                        SELECT p.product_id, p.name, p.price, p.category, p.subcategory, 
                               p.image_path, p.description, p.stock, w.created_at as saved_at
                        FROM wishlist w
                        JOIN products p ON w.product_id = p.product_id
                        WHERE w.user_id = %s
                        ORDER BY w.created_at DESC
                    ''', (user_id,))
                    rows = cursor.fetchall()
                    results = []
                    for r in rows:
                        item = dict(r)
                        item['price'] = float(item['price']) if item.get('price') is not None else 0.0
                        if 'saved_at' in item and item['saved_at']:
                            val = item['saved_at']
                            if isinstance(val, str):
                                try:
                                    val = datetime.fromisoformat(val)
                                except Exception:
                                    pass
                            if hasattr(val, 'strftime'):
                                item['saved_at'] = val.strftime('%b %d, %Y')
                        results.append(item)
                    return results
        except DatabaseError as e:
            logger.error(f"Error retrieving wishlist for user #{user_id}: {e}")
            return []

    @staticmethod
    def toggle_item(user_id: int, product_id: int) -> Tuple[bool, str, bool, int]:
        """
        Toggle product in user's wishlist (add if not present, remove if already present).

        Returns:
            Tuple of (success, message, in_wishlist, updated_count).
        """
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    # Check if already in wishlist
                    cursor.execute(
                        "SELECT id FROM wishlist WHERE user_id = %s AND product_id = %s",
                        (user_id, product_id)
                    )
                    existing = cursor.fetchone()

                    if existing:
                        cursor.execute(
                            "DELETE FROM wishlist WHERE user_id = %s AND product_id = %s",
                            (user_id, product_id)
                        )
                        in_wishlist = False
                        message = "Removed from wishlist"
                    else:
                        cursor.execute(
                            "INSERT INTO wishlist (user_id, product_id) VALUES (%s, %s)",
                            (user_id, product_id)
                        )
                        in_wishlist = True
                        message = "Added to wishlist"

                    cursor.execute("SELECT COUNT(*) FROM wishlist WHERE user_id = %s", (user_id,))
                    count = cursor.fetchone()[0]

            clear_wishlist_cache(user_id)
            logger.info(f"User #{user_id} toggled product #{product_id} (now in_wishlist={in_wishlist})")
            return True, message, in_wishlist, count
        except DatabaseError as e:
            logger.error(f"Error toggling wishlist item for user #{user_id}, product #{product_id}: {e}")
            return False, "Failed to update wishlist", False, 0

    @staticmethod
    def remove_item(user_id: int, product_id: int) -> Tuple[bool, str, int]:
        """
        Explicitly remove an item from user's wishlist.

        Returns:
            Tuple of (success, message, updated_count).
        """
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        "DELETE FROM wishlist WHERE user_id = %s AND product_id = %s",
                        (user_id, product_id)
                    )
                    cursor.execute("SELECT COUNT(*) FROM wishlist WHERE user_id = %s", (user_id,))
                    count = cursor.fetchone()[0]

            clear_wishlist_cache(user_id)
            return True, "Item removed from wishlist", count
        except DatabaseError as e:
            logger.error(f"Error removing wishlist item for user #{user_id}, product #{product_id}: {e}")
            return False, "Failed to remove item", 0

