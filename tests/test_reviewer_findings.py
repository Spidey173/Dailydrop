"""
Tests verifying and testing fixes for Task 7 reviewer findings:
- 7a: GET /api/v1/orders/<order_id>/status must be read-only (not mutate status)
- 7b: TrafficSimulator daemon opt-in via ENABLE_TRAFFIC_SIMULATOR
- 7c: Empty states instead of fake hardcoded cohort/market-basket/RFM fallbacks
"""
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock
from app import create_app
from database import get_db_connection, get_unified_analytics, clear_analytics_cache
from services.order_service import OrderService
from services.auth_service import AuthService


@pytest.fixture
def test_client():
    app = create_app('testing')
    app.config['WTF_CSRF_ENABLED'] = False
    with app.test_client() as client:
        with app.app_context():
            yield client


def test_order_status_get_is_read_only(test_client):
    """
    7a: GET /api/v1/orders/<order_id>/status must be strictly read-only.
    Even when tracking indicates the delivery window has elapsed, GET must not mutate orders.status.
    """
    # 1. Fetch real product from DB
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT product_id, name, price FROM products LIMIT 1")
            prod = cur.fetchone()
            pid = prod['product_id'] if isinstance(prod, dict) else prod[0]
            pname = prod['name'] if isinstance(prod, dict) else prod[1]
            pprice = float(prod['price'] if isinstance(prod, dict) else prod[2])

    # 2. Create customer and order
    _, _, user_id = AuthService.register_user('Readonly Tester', 'readonly@example.com', 'Password@1234')
    cart = [{'product_id': pid, 'name': pname, 'price': pprice, 'quantity': 1}]
    ok, msg, order_id = OrderService.create_order(
        user_id=user_id,
        full_name='Readonly Tester',
        phone_number='9876543210',
        address='123 Track Way',
        products=cart,
        total_amount=pprice,
        status='Processing'
    )
    assert ok is True

    # 3. Backdate the order to 20 minutes ago (so is_delivered is True in tracking)
    past_time = datetime.now(timezone.utc) - timedelta(minutes=20)
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE orders SET order_date = %s WHERE order_id = %s", (past_time, order_id))

    # Authenticate session
    with test_client.session_transaction() as sess:
        sess['user_id'] = user_id
        sess['name'] = 'Readonly Tester'
        sess['user_role'] = 'customer'

    # 4. Call GET /api/v1/orders/<order_id>/status
    res = test_client.get(f'/api/v1/orders/{order_id}/status')
    assert res.status_code == 200

    # 5. Verify order status in database is STILL 'Processing' (NOT mutated by GET)
    order_in_db = OrderService.get_order_by_id(order_id)
    assert order_in_db['status'] == 'Processing', f"GET mutated status to {order_in_db['status']}!"


def test_traffic_simulator_daemon_disabled_by_default():
    """
    7b: By default, TrafficSimulatorService.start_daemon must NOT be called on boot.
    """
    with patch("services.traffic_simulator_service.TrafficSimulatorService.start_daemon") as mock_start:
        app = create_app('development')
        mock_start.assert_not_called()


def test_no_fake_analytics_fallbacks(test_client):
    """
    7c: When there is no real order data, analytics functions must return empty lists,
    not hardcoded hallucinated arrays (_DEFAULT_CUSTOMER_PROFILES, fake cohorts, fake baskets).
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM order_items")
            cur.execute("DELETE FROM orders")
    clear_analytics_cache()
    analytics = get_unified_analytics(days=30)
    assert analytics['cohort_matrix'] == []
    assert analytics['market_basket'] == []
    assert analytics['rfm_customers'] == []
