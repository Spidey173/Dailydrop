"""
Inventory reservation service.
Defines PostgreSQL as the authoritative single source of truth for all inventory levels,
with Redis serving as a discardable, sub-millisecond fast-fail cache.

Includes:
1. Two-tier stock reservation (Redis Lua fast-fail -> PostgreSQL ACID lock).
2. Automatic compensating rollback of Redis cache mutations upon any DB commit failure.
3. Active reconciliation mechanism: re-syncs or evicts Redis cache keys to reflect PostgreSQL truth.
"""
import logging
from typing import Any, Dict, List, Optional, Tuple
from services.redis_service import RedisService

logger = logging.getLogger(__name__)


class InventoryReservationService:
    """
    Manages multi-tier inventory reservation across Redis and PostgreSQL.
    
    ARCHITECTURAL PRINCIPLE:
    - PostgreSQL is the SINGLE SOURCE OF TRUTH (SSOT).
    - Redis is an ephemeral fast-rejection cache used to protect the relational database
      during concurrent traffic surges (e.g., flash sales).
    - If a failure, exception, crash, or constraint violation occurs between cache mutation
      and database commit, the Redis cache mutation is rolled back or reconciled to match PostgreSQL.
    """

    @classmethod
    def reserve_inventory(
        cls,
        cursor: Any,
        conn: Any,
        item_quantities: Dict[int, int]
    ) -> Tuple[bool, Optional[str], Dict[int, int]]:
        """
        Reserves inventory across Redis memory (sub-millisecond fast fail)
        and ACID relational PostgreSQL.

        Returns:
            Tuple of (success, error_message, redis_decrements)
        """
        redis_decrements: Dict[int, int] = {}

        # 1. Distributed Redis Lua Script (< 1ms fast-fail)
        for r_pid, required_qty in item_quantities.items():
            cursor.execute("SELECT name, stock FROM products WHERE product_id = %s", (r_pid,))
            p_info = cursor.fetchone()
            avail_stock = (p_info['stock'] if isinstance(p_info, dict) else p_info[1]) if p_info else None
            p_name = (p_info['name'] if isinstance(p_info, dict) else p_info[0]) if p_info else f"Product #{r_pid}"

            success, msg, rem = RedisService.atomic_decrement_stock(
                product_id=r_pid,
                quantity=required_qty,
                fallback_db_stock=avail_stock
            )
            if not success:
                cls.rollback_reservations(redis_decrements)
                logger.warning(f"[Flash-Sale Fast Reject] Insufficient stock in Redis for '{p_name}' (available {rem}, requested {required_qty})")
                return False, f"Insufficient stock for '{p_name}'. Only {rem} units left in stock.", redis_decrements

            redis_decrements[r_pid] = required_qty

        # 2. Relational PostgreSQL Atomic Update (Authoritative Source of Truth):
        # UPDATE products SET stock = stock - %s WHERE product_id = %s AND stock >= %s
        for r_pid, required_qty in item_quantities.items():
            cursor.execute(
                "UPDATE products SET stock = stock - %s WHERE product_id = %s AND stock >= %s",
                (required_qty, r_pid, required_qty)
            )
            if cursor.rowcount == 0:
                cursor.execute("SELECT name, stock FROM products WHERE product_id = %s", (r_pid,))
                p_info = cursor.fetchone()
                p_name = (p_info['name'] if isinstance(p_info, dict) else p_info[0]) if p_info else f"Product #{r_pid}"
                avail_stock = (p_info['stock'] if isinstance(p_info, dict) else p_info[1]) if p_info else 0
                conn.rollback()
                cls.rollback_reservations(redis_decrements)
                logger.warning(f"Overselling prevented: Insufficient stock for '{p_name}' (requested {required_qty}, available {avail_stock})")
                return False, f"Insufficient stock for '{p_name}'. Only {avail_stock} units left in stock.", redis_decrements

        return True, None, redis_decrements

    @classmethod
    def rollback_reservations(cls, redis_decrements: Dict[int, int]) -> None:
        """
        Compensates any prior items decremented in Redis memory.
        Ensures that if DB transaction aborts or fails before commit,
        Redis cache is restored immediately.
        """
        for rolled_pid, rolled_qty in redis_decrements.items():
            try:
                RedisService.atomic_rollback_stock(rolled_pid, rolled_qty)
            except Exception as e:
                logger.error(f"Failed to rollback Redis stock for product #{rolled_pid}: {e}")

    @classmethod
    def reconcile_stock_with_database(cls, cursor: Any, product_ids: Optional[List[int]] = None) -> Dict[str, Any]:
        """
        Actively audits and synchronizes Redis cached inventory with PostgreSQL authoritative records.
        Corrects any cache drift caused by hard crashes between cache mutation and DB commit.

        Returns:
            Dict summarizing checked, drifted, and corrected items.
        """
        if product_ids:
            format_strings = ','.join(['%s'] * len(product_ids))
            cursor.execute(f"SELECT product_id, stock FROM products WHERE product_id IN ({format_strings})", tuple(product_ids))
        else:
            cursor.execute("SELECT product_id, stock FROM products")

        db_rows = cursor.fetchall()
        report = {'checked': 0, 'synced': 0, 'discrepancies': []}

        for row in db_rows:
            pid = row['product_id'] if isinstance(row, dict) else row[0]
            db_stock = row['stock'] if isinstance(row, dict) else row[1]
            report['checked'] += 1

            cached_stock = RedisService.get_stock(pid)
            if cached_stock is not None and cached_stock != db_stock:
                report['discrepancies'].append({
                    'product_id': pid,
                    'redis_stock': cached_stock,
                    'authoritative_db_stock': db_stock
                })
                # Re-align Redis to match the authoritative PostgreSQL database
                RedisService.set_stock(pid, db_stock)
                report['synced'] += 1

        return report
