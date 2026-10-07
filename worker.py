#!/usr/bin/env python
"""
DailyDrop Asynchronous Background Task Worker.

Listens on the Redis 'dailydrop_tasks' queue and processes jobs asynchronously:
1. Automated invoice PDF generation.
2. Email dispatch with exponential backoff retries.
3. Inventory stock threshold health monitoring.
4. Transactional Outbox reconciliation.

Run via:
    python worker.py
Or in burst mode (processes remaining queue and exits):
    python worker.py --burst
"""

import sys
import logging
from config import Config
from services.redis_service import RedisService

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(process)d] - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("dailydrop.worker")


def main():
    logger.info("Initializing DailyDrop Redis Background Worker...")

    client = RedisService.get_raw_client()
    if not client:
        logger.error("Cannot start worker: Redis connection unavailable.")
        sys.exit(1)

    try:
        from rq import Worker, Queue
        from rq.registry import FailedJobRegistry

        queue_name = "dailydrop_tasks"
        queue = Queue(queue_name, connection=client)
        failed_registry = FailedJobRegistry(queue=queue)

        logger.info(f"Connected to Redis broker. Listening on queue '{queue_name}'...")
        logger.info(f"Failed Job (DLQ) count: {len(failed_registry)}")

        burst_mode = "--burst" in sys.argv
        worker = Worker([queue], connection=client)
        worker.work(burst=burst_mode)

    except KeyboardInterrupt:
        logger.info("Worker stopped by user.")
    except Exception as e:
        logger.error(f"Fatal worker exception: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
