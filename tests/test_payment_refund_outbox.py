"""
Tests for automatic REFUND_REQUIRED outbox event recording when order creation fails post-payment.
"""
import json
import pytest
from unittest.mock import patch
from app import create_app
from database import get_db_connection
from psycopg2.extras import RealDictCursor
from repositories.order_repository import save_pending_order
from services.auth_service import AuthService
from services.outbox_service import OutboxService
from services.order_service import OrderService


@pytest.fixture
def client():
    app = create_app('testing')
    app.config['WTF_CSRF_ENABLED'] = False
    app.config['DEMO_PAYMENTS'] = True
    with app.test_client() as c:
        with app.app_context():
            yield c


def test_refund_required_outbox_event_on_order_creation_failure(client, monkeypatch):
    """
    When a payment signature is verified (payment captured) but OrderService.create_order fails
    (e.g., flash-sale stock depletion), a REFUND_REQUIRED event must be atomically recorded in outbox_events.
    """
    monkeypatch.setenv('DEMO_PAYMENTS', 'true')
    # 1. Setup user
    _, _, user_id = AuthService.register_user('Refund Tester', 'refund_tester@example.com', 'Password@1234')

    with client.session_transaction() as sess:
        sess['user_id'] = user_id
        sess['name'] = 'Refund Tester'
        sess['email'] = 'refund_tester@example.com'
        sess['user_role'] = 'customer'

    # 2. Setup product and pending order
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT product_id, name, price FROM products LIMIT 1")
            prod = cur.fetchone()
            pid = prod['product_id'] if isinstance(prod, dict) else prod[0]
            pname = prod['name'] if isinstance(prod, dict) else prod[1]
            price = float(prod['price'] if isinstance(prod, dict) else prod[2])

    rzp_order_id = "order_refund_test_999"
    rzp_pay_id = "pay_refund_test_888"
    demo_sig = f"demo_auto_verified_{rzp_order_id}"
    cart = [{"product_id": pid, "name": pname, "price": price, "quantity": 1}]

    final_total = price + 30.00  # including delivery fee for subtotal < 500
    save_pending_order(
        razorpay_order_id=rzp_order_id,
        user_id=user_id,
        full_name='Refund Tester',
        phone_number='9876543210',
        address='456 Refund St',
        products=cart,
        total_amount=final_total
    )

    # 3. Mock OrderService.create_order to simulate failure (e.g. stock exhausted)
    with patch("services.order_service.OrderService.create_order", return_value=(False, "Insufficient stock", None)):
        res = client.post('/api/verify-payment', json={
            'razorpay_order_id': rzp_order_id,
            'razorpay_payment_id': rzp_pay_id,
            'razorpay_signature': demo_sig,
            'products': cart,
            'full_name': 'Refund Tester',
            'phone_number': '9876543210',
            'address': '456 Refund St'
        })

    # Response must clearly communicate refund initiated
    assert res.status_code in (400, 422, 500)
    data = res.get_json()
    assert data['success'] is False
    assert 'refund' in data.get('message', '').lower() or data.get('refund_status') == 'INITIATED'

    # Check that REFUND_REQUIRED event exists in outbox_events table
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM outbox_events WHERE event_type = 'REFUND_REQUIRED'")
            rows = cur.fetchall()

    assert len(rows) >= 1
    refund_event = next(r for r in rows if (r['aggregate_id'] if isinstance(r, dict) else r['aggregate_id']) == rzp_pay_id)
    payload = json.loads(refund_event['payload']) if isinstance(refund_event['payload'], str) else refund_event['payload']
    assert payload['payment_id'] == rzp_pay_id
    assert payload['user_id'] == user_id
    assert 'Insufficient stock' in payload['reason']
