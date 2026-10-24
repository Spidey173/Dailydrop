"""
Inventory reservation service.
Handles distributed Redis Lua atomic decrements and relational PostgreSQL row-level reservations.
"""
import logging
from typing import Any, Dict, Optional, Tuple
from services.redis_service import RedisService

logger = logging.getLogger(__name__)


class InventoryReservationService:
    """Manages multi-tier inventory reservation across Redis and PostgreSQL."""

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

        # 1. Distributed Redis Lua Script (< 1ms)
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

        # 2. Relational PostgreSQL Atomic Update:
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
        """Compensates any prior items decremented in Redis memory."""
        for rolled_pid, rolled_qty in redis_decrements.items():
            try:
                RedisService.atomic_rollback_stock(rolled_pid, rolled_qty)
            except Exception as e:
                logger.error(f"Failed to rollback Redis stock for product #{rolled_pid}: {e}")
