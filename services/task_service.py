"""
Task Dispatcher Service.

Enqueues asynchronous tasks onto Redis-backed worker queues with exponential retries and Dead-Letter Queue (DLQ) support.
Falls back safely to synchronous or non-blocking dispatch if Redis is disabled or offline.
"""

import logging
from typing import Optional, List
from services.redis_service import RedisService

logger = logging.getLogger(__name__)

QUEUE_NAME = "dailydrop_tasks"


class TaskService:
    """Dispatches background tasks to Redis Queue (RQ)."""

    @classmethod
    def get_queue(cls):
        """Get or initialize the RQ queue using the shared Redis connection."""
        try:
            from rq import Queue
            client = RedisService.get_raw_client()
            if client is None:
                return None
            return Queue(QUEUE_NAME, connection=client)
        except Exception as e:
            logger.warning(f"Could not initialize RQ Queue: {e}")
            return None

    @classmethod
    def enqueue_order_confirmation(
        cls,
        order_id: int,
        recipient_name: str,
        recipient_email: Optional[str],
        total_amount: float,
        payment_method: str = "COD"
    ) -> bool:
        """Enqueue order receipt and confirmation dispatch."""
        try:
            import tasks
            queue = cls.get_queue()
            if queue:
                try:
                    from rq import Retry
                    retry_arg = Retry(max=3, interval=[10, 30, 60])
                except (ImportError, ModuleNotFoundError):
                    retry_arg = None

                enqueue_kwargs = {'job_timeout': '3m'}
                if retry_arg is not None:
                    enqueue_kwargs['retry'] = retry_arg

                job = queue.enqueue(
                    tasks.send_order_confirmation_task,
                    args=(order_id, recipient_name, recipient_email, total_amount, payment_method),
                    **enqueue_kwargs
                )
                logger.info(f"Enqueued order confirmation task [Job ID: {getattr(job, 'id', 'mock_id')}] for Order #{order_id}")
                return True
            else:
                # Inline fallback if Redis is down or rq is not installed
                logger.info(f"Executing order confirmation inline (Redis queue bypassed) for Order #{order_id}")
                tasks.send_order_confirmation_task(
                    order_id, recipient_name, recipient_email, total_amount, payment_method
                )
                return True
        except Exception as e:
            logger.error(f"Failed to dispatch order confirmation task for Order #{order_id}: {e}")
            return False

    @classmethod
    def enqueue_low_stock_check(cls, product_ids: List[int]) -> bool:
        """Enqueue background check for low stock levels."""
        if not product_ids:
            return True
        try:
            import tasks
            queue = cls.get_queue()
            if queue:
                job = queue.enqueue(
                    tasks.check_low_stock_alerts_task,
                    args=(product_ids,),
                    job_timeout='2m'
                )
                logger.info(f"Enqueued low-stock alert task [Job ID: {job.id}] for {len(product_ids)} products")
                return True
            else:
                tasks.check_low_stock_alerts_task(product_ids)
                return True
        except Exception as e:
            logger.error(f"Failed to dispatch low-stock alert task: {e}")
            return False
