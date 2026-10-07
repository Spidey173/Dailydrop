"""
Asynchronous Worker Tasks for Daily Drop.

Executed by the background worker process (Celery / RQ) to decouple
post-checkout side-effects from the user-facing HTTP request thread.
"""

import logging
import time
from typing import List, Optional, Dict, Any

logger = logging.getLogger("dailydrop.worker")


def send_order_confirmation_task(
    order_id: int,
    recipient_name: str,
    recipient_email: Optional[str],
    total_amount: float,
    payment_method: str = "COD"
) -> Dict[str, Any]:
    """
    Background Task: Process post-order confirmation, invoice receipt generation, and customer notification.
    """
    logger.info(f"[Worker] Processing order confirmation for Order #{order_id} to {recipient_name} ({recipient_email or 'phone'}). Amount: ₹{total_amount:.2f}")

    # 1. Simulate fast PDF invoice generation
    time.sleep(0.05)
    invoice_number = f"INV-2026-{order_id:06d}"

    # 2. Simulate email / SMS delivery with resilience
    logger.info(f"[Worker] Receipt generated: {invoice_number}. Dispatching notification to {recipient_email or 'customer'}...")

    return {
        "status": "delivered",
        "order_id": order_id,
        "invoice_number": invoice_number,
        "recipient": recipient_email or recipient_name,
        "processed_at": time.time()
    }


def check_low_stock_alerts_task(product_ids: List[int]) -> List[Dict[str, Any]]:
    """
    Background Task: Inspect stock counts for purchased products and dispatch low-stock alerts to admin.
    """
    if not product_ids:
        return []

    from database import get_db_connection
    from psycopg2.extras import RealDictCursor

    alerts = []
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                format_strings = ','.join(['%s'] * len(product_ids))
                cursor.execute(
                    f"SELECT product_id, name, stock FROM products WHERE product_id IN ({format_strings})",
                    tuple(product_ids)
                )
                rows = cursor.fetchall()
                for row in rows:
                    p = dict(row)
                    stock = p.get('stock', 0)
                    if stock <= 10:
                        logger.warning(
                            f"[Worker Alert] ⚠️ LOW STOCK WARNING: Product '{p.get('name')}' (#{p.get('product_id')}) has only {stock} units left!"
                        )
                        alerts.append({
                            "product_id": p.get('product_id'),
                            "name": p.get('name'),
                            "stock": stock,
                            "severity": "CRITICAL" if stock < 5 else "WARNING"
                        })
    except Exception as e:
        logger.error(f"[Worker] Error checking low stock in background: {e}")

    return alerts
