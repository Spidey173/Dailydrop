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
import os
import logging
from services.redis_service import RedisService

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(process)d] - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("dailydrop.worker")


def main():
    logger.info("Initializing DailyDrop Redis Background Worker...")

    try:
        from rq import Queue
        from rq.worker.worker_classes import SimpleWorker, Worker
        from rq.registry import FailedJobRegistry
    except (ImportError, ModuleNotFoundError) as err:
        logger.error(
            "Cannot start worker: Required dependency 'rq' is not installed in the active Python environment.\n"
            "Please activate the virtual environment and install dependencies:\n"
            "    source venv/bin/activate && pip install -r requirements.txt"
        )
        sys.exit(1)

    client = RedisService.get_raw_client()
    if not client:
        logger.error("Cannot start worker: Redis connection unavailable.")
        sys.exit(1)

    try:
        queue_name = "dailydrop_tasks"
        queue = Queue(queue_name, connection=client)
        failed_registry = FailedJobRegistry(queue=queue)

        logger.info(f"Connected to Redis broker. Listening on queue '{queue_name}'...")
        logger.info(f"Failed Job (DLQ) count: {len(failed_registry)}")

        burst_mode = "--burst" in sys.argv

        # On macOS and Windows, forking multi-threaded SSL/PostgreSQL connections causes SIGSEGV (signal 11).
        # SimpleWorker executes jobs safely in-process without os.fork().
        use_simple = sys.platform == 'darwin' or os.name == 'nt' or '--simple' in sys.argv
        WorkerClass = SimpleWorker if use_simple else Worker
        logger.info(f"Worker engine selected: {WorkerClass.__name__}")

        worker = WorkerClass([queue], connection=client)
        worker.work(burst=burst_mode)

    except KeyboardInterrupt:
        logger.info("Worker stopped by user.")
    except Exception as e:
        logger.error(f"Fatal worker exception: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()

