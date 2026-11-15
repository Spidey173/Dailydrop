"""
Tests for DailyDrop Distributed Architecture & Production Upgrades:
1. Flash-Sale Concurrency: Distributed Redis Stock Lua Scripts (< 1ms).
2. Client-Side Idempotency Keys: Duplicate order and double-charge prevention.
3. Read-Through Redis Caching: Catalog cache hydration & invalidation.
4. Asynchronous Task Queue: Celery / RQ worker task execution.
5. Transactional Outbox Pattern: Atomic event creation and relaying.
"""

import uuid
from datetime import datetime, timezone, timedelta
import pytest
from services.redis_service import RedisService
from services.idempotency_service import IdempotencyService
from services.outbox_service import OutboxService
from services.task_service import TaskService
from app import create_app
from database import get_all_products, get_product_by_id, update_product_stock, get_db_connection, clear_product_cache


@pytest.fixture
def client():
    app = create_app('testing')
    app.config['WTF_CSRF_ENABLED'] = False
    with app.test_client() as c:
        yield c


def test_redis_service_unmocked_methods_have_no_name_error():
    """Verify that unmocked get_client() and get_raw_client() do not raise NameError due to missing imports."""
    from config import Config
    from services.redis_service import RedisService

    orig_enabled = Config.REDIS_ENABLED
    orig_url = Config.REDIS_URL
    try:
        Config.REDIS_ENABLED = True
        Config.REDIS_URL = 'redis://127.0.0.1:9999/0'
        # Pointed at unreachable port; must return None or fail with connection error, NEVER NameError
        client = RedisService._real_get_client()
        assert client is None
        raw_client = RedisService._real_get_raw_client()
        assert raw_client is None
    finally:
        Config.REDIS_ENABLED = orig_enabled
        Config.REDIS_URL = orig_url


class TestFlashSaleConcurrency:
    """Tests for distributed Lua stock decrements and fast out-of-stock rejection."""

    def test_atomic_lua_stock_decrement(self):
        """Test atomic decrement via Redis Lua script."""
        test_pid = 88001
        RedisService.set_stock(test_pid, 10)
        
        # Decrement 3 units
        success, msg, rem = RedisService.atomic_decrement_stock(test_pid, 3)
        assert success is True
        assert rem == 7
        assert RedisService.get_stock(test_pid) == 7

        # Decrement remaining 7 units
        success, msg, rem = RedisService.atomic_decrement_stock(test_pid, 7)
        assert success is True
        assert rem == 0

        # Attempt to decrement when out of stock
        success, msg, rem = RedisService.atomic_decrement_stock(test_pid, 1)
        assert success is False
        assert "Insufficient stock" in msg
        assert rem == 0

        # Cleanup
        RedisService.delete(RedisService.stock_key(test_pid))

    def test_atomic_lua_stock_rollback(self):
        """Test atomic stock rollback upon transaction cancellation."""
        test_pid = 88002
        RedisService.set_stock(test_pid, 15)

        # Decrement 5 units
        success, _, rem = RedisService.atomic_decrement_stock(test_pid, 5)
        assert success is True
        assert rem == 10

        # Rollback 5 units
        rolled_back = RedisService.atomic_rollback_stock(test_pid, 5)
        assert rolled_back is True
        assert RedisService.get_stock(test_pid) == 15

        # Cleanup
        RedisService.delete(RedisService.stock_key(test_pid))


class TestIdempotencyService:
    """Tests for client idempotency key handling and duplicate checkout rejection."""

    def test_idempotency_workflow(self):
        """Test complete lifecycle: acquire -> conflict while processing -> complete -> replay."""
        key = f"test_idem_{uuid.uuid4().hex}"

        # 1. First acquire: must succeed
        can_proceed, resp, status = IdempotencyService.acquire(key, user_id=1)
        assert can_proceed is True
        assert resp is None
        assert status is None

        # 2. Concurrent second acquire while still processing: must return 409 Conflict
        can_proceed2, resp2, status2 = IdempotencyService.acquire(key, user_id=1)
        assert can_proceed2 is False
        assert status2 == 409
        assert resp2['error'] == 'Conflict'

        # 3. Complete the request
        mock_response = {'success': True, 'order_id': 999, 'message': 'Order placed successfully'}
        IdempotencyService.complete(key, mock_response, status_code=200)

        # 4. Third acquire: should detect COMPLETED and replay cached response without re-executing
        can_proceed3, resp3, status3 = IdempotencyService.acquire(key, user_id=1)
        assert can_proceed3 is False
        assert status3 == 200
        assert resp3['order_id'] == 999
        assert resp3['success'] is True

        # Cleanup
        IdempotencyService.release(key)

    def test_place_order_idempotency_endpoint(self, client):
        """Test HTTP endpoint behavior when sending Idempotency-Key header on checkout."""
        # Log in customer session
        with client.session_transaction() as sess:
            sess['user_id'] = 2
            sess['name'] = 'Demo Customer'
            sess['email'] = 'demo_dailydrop@gmail.com'

        idempotency_key = f"key_{uuid.uuid4().hex}"
        order_payload = {
            'full_name': 'Demo Customer',
            'phone_number': '9876543210',
            'address': '42 Test Way, Floor 3',
            'payment_method': 'COD',
            'products': [
                {'product_id': 1, 'name': 'Fresh Milk', 'price': 60.0, 'quantity': 1}
            ]
        }

        headers = {'Idempotency-Key': idempotency_key}

        # First checkout attempt
        res1 = client.post('/place_order', json=order_payload, headers=headers)
        assert res1.status_code == 200
        data1 = res1.get_json()
        assert data1['success'] is True
        order_id_1 = data1['order_id']

        # Second checkout attempt with EXACT same Idempotency-Key (simulating accidental double-click)
        res2 = client.post('/place_order', json=order_payload, headers=headers)
        assert res2.status_code == 200
        data2 = res2.get_json()
        assert data2['success'] is True
        # Must return the EXACT SAME order_id rather than creating a second duplicate order!
        assert data2['order_id'] == order_id_1

        # Cleanup
        IdempotencyService.release(idempotency_key)


class TestReadThroughCatalogCaching:
    """Tests for Redis read-through catalog caching and cache invalidation."""

    def test_read_through_catalog_cache(self):
        """Verify products are cached in Redis and served with low latency."""
        # Invalidate existing cache
        clear_product_cache()

        # 1. First fetch: loads from database and hydrates Redis
        products1 = get_all_products()
        assert len(products1) > 0

        # Check that Redis contains the cached catalog JSON
        cached_json = RedisService.get_json('catalog:all_products')
        assert cached_json is not None
        assert len(cached_json) == len(products1)

        # 2. Second fetch: served from Redis
        products2 = get_all_products()
        assert len(products2) == len(products1)

    def test_cache_invalidation_on_stock_update(self):
        """Updating stock must invalidate catalog cache and synchronize Redis stock key."""
        prods = get_all_products()
        if not prods:
            return
        target_pid = prods[0]['product_id']
        old_stock = prods[0].get('stock', 50)
        new_stock = old_stock + 5

        update_product_stock(target_pid, new_stock)

        # Redis stock key should reflect the updated stock
        assert RedisService.get_stock(target_pid) == new_stock

        # In-memory and Redis catalog should have been invalidated and re-hydrated
        updated_prod = get_product_by_id(target_pid)
        assert updated_prod is not None
        assert updated_prod['stock'] == new_stock


class TestTransactionalOutboxAndAsyncQueue:
    """Tests for Transactional Outbox atomic recording and background task enqueuing."""

    def test_outbox_event_lifecycle(self):
        """Test recording an outbox event, fetching pending, and marking processed."""
        test_order_id = 99991
        event_id = None

        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                event_id = OutboxService.record_event(
                    cursor=cursor,
                    event_type='ORDER_CREATED',
                    aggregate_type='order',
                    aggregate_id=test_order_id,
                    payload={'order_id': test_order_id, 'amount': 99.0, 'customer': 'Test User'}
                )

        assert event_id is not None
        assert event_id.startswith('evt_')

        # Fetch pending events
        pending = OutboxService.fetch_pending_events(limit=10)
        found = [e for e in pending if e['event_id'] == event_id]
        assert len(found) == 1
        assert found[0]['event_type'] == 'ORDER_CREATED'
        assert found[0]['status'] == 'PENDING'

        # Relay / process event
        OutboxService.mark_processed(event_id)

        # Ensure no longer in pending
        pending_after = OutboxService.fetch_pending_events(limit=50)
        found_after = [e for e in pending_after if e['event_id'] == event_id]
        assert len(found_after) == 0

    def test_task_queue_dispatch(self):
        """Verify TaskService enqueues background tasks cleanly."""
        enqueued = TaskService.enqueue_order_confirmation(
            order_id=7777,
            recipient_name='Async Tester',
            recipient_email='async@dailydrop.com',
            total_amount=249.0,
            payment_method='COD'
        )
        assert enqueued is True

        enqueued_stock = TaskService.enqueue_low_stock_check([1, 2])
        assert enqueued_stock is True

    def test_outbox_stale_claim_recovery(self):
        """
        Verify that claim_pending_events re-claims stale IN_PROGRESS events
        whose claimed_at is older than 10 minutes, but ignores fresh IN_PROGRESS events.
        """
        now = datetime.now(timezone.utc)
        stale_time = now - timedelta(minutes=15)
        fresh_time = now - timedelta(minutes=2)

        stale_event_id = f"evt_stale_{uuid.uuid4().hex[:8]}"
        fresh_event_id = f"evt_fresh_{uuid.uuid4().hex[:8]}"

        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                # Insert stale IN_PROGRESS event (claimed 15m ago)
                cursor.execute(
                    """
                    INSERT INTO outbox_events (event_id, event_type, aggregate_type, aggregate_id, payload, status, claimed_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (stale_event_id, 'TEST_EVENT', 'order', '101', '{"test": 1}', 'IN_PROGRESS', stale_time)
                )
                # Insert fresh IN_PROGRESS event (claimed 2m ago)
                cursor.execute(
                    """
                    INSERT INTO outbox_events (event_id, event_type, aggregate_type, aggregate_id, payload, status, claimed_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (fresh_event_id, 'TEST_EVENT', 'order', '102', '{"test": 2}', 'IN_PROGRESS', fresh_time)
                )

        # Claim events
        claimed = OutboxService.claim_pending_events(limit=50)
        claimed_ids = [e['event_id'] for e in claimed]

        # Stale event MUST be re-claimed; fresh event MUST NOT be re-claimed
        assert stale_event_id in claimed_ids, "Stale IN_PROGRESS event was not re-claimed!"
        assert fresh_event_id not in claimed_ids, "Fresh IN_PROGRESS event was incorrectly re-claimed!"
