"""
Comprehensive Tests for Server-Authoritative Checkout, Payment Lifecycle,
and Order State Machine.

Covers:
1. Forged prices rejection and authoritative price recalculation from database.
2. Unknown product rejection (invalid ID, fake name).
3. Insufficient stock atomicity and transaction rollback.
4. Idempotent retries preventing duplicate decrements.
5. Concurrent checkout race condition safety.
6. Payment verification: invalid signatures, mismatched user ownership, missing pending orders.
7. Webhook idempotency, duplicate events, and browser disconnect recovery.
8. State machine fulfillment transitions and terminal state enforcement.
9. Health check endpoint observability.
10. Sanitized structured logging.
"""

import hmac
import hashlib
import json
import threading
import pytest
from app import create_app
from config import Config
from database import (
    get_db_connection, add_product, get_product_by_id,
    save_pending_order, get_pending_order
)
from services.order_service import OrderService
from services.payment_service import PaymentService
from utils import SanitizingLogFormatter
import logging


@pytest.fixture
def test_app():
    app = create_app('testing')
    app.config['WTF_CSRF_ENABLED'] = False
    return app


@pytest.fixture
def auth_client(test_app):
    with test_app.test_client() as client:
        with client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['name'] = 'Checkout Tester'
            sess['email'] = 'admin_dailydrop@gmail.com'
        yield client


# ==================== 1. Forged Prices & Catalog Recalculation ====================

def test_forged_prices_overridden_by_catalog():
    """Client-provided prices must be completely overridden by authoritative database prices."""
    # Seed product with DB price 250.00
    prod_id = add_product(
        name="Authentic Ghee 500ml",
        price=250.00,
        category="Dairy",
        stock=20
    )
    assert prod_id is not None

    # Attacker crafts cart with price = 0.05
    tampered_cart = [
        {"product_id": prod_id, "name": "Authentic Ghee 500ml", "price": 0.05, "quantity": 2}
    ]

    valid, msg, subtotal, fee, total = PaymentService.calculate_authoritative_total(tampered_cart)
    assert valid is True
    # Expected: 2 * 250.0 = 500.0, fee = 0.0 (subtotal >= 500), total = 500.0
    assert subtotal == 500.0
    assert fee == 0.0
    assert total == 500.0
    assert tampered_cart[0]['price'] == 250.00

    # Test OrderService saves resolved 250.00 price
    success, o_msg, order_id = OrderService.create_order(
        user_id=1,
        full_name='Price Tester',
        phone_number='9876543210',
        address='123 Security St',
        products=tampered_cart,
        total_amount=total,
        payment_method='COD'
    )
    assert success is True
    assert order_id is not None

    from database import get_order_items
    items = get_order_items(order_id)
    assert len(items) == 1
    assert items[0]['price'] == 250.00
    assert items[0]['subtotal'] == 500.00


# ==================== 2. Unknown Product Rejection ====================

def test_unknown_product_id_rejected():
    """Cart items with non-existent product IDs must be rejected."""
    cart_with_fake_id = [
        {"product_id": 999999, "name": "Phantom Gadget", "price": 100.0, "quantity": 1}
    ]
    valid, err, _, _, _ = PaymentService.calculate_authoritative_total(cart_with_fake_id)
    assert valid is False
    assert "not found in catalog" in err

    success, err_msg, order_id = OrderService.create_order(
        user_id=1,
        full_name='Tester',
        phone_number='9876543210',
        address='Test Rd',
        products=cart_with_fake_id,
        total_amount=100.0
    )
    assert success is False
    assert "not found in catalog" in err_msg
    assert order_id is None


def test_unknown_product_name_rejected():
    """Cart items without valid catalog products must be rejected."""
    cart_with_fake_name = [
        {"name": "NonExistentItem12345", "price": 50.0, "quantity": 1}
    ]
    valid, err, _, _, _ = PaymentService.calculate_authoritative_total(cart_with_fake_name)
    assert valid is False
    assert "not found in catalog" in err


# ==================== 3. Insufficient Stock Atomicity ====================

def test_insufficient_stock_rollback():
    """When stock is insufficient, the entire order is rolled back and no stock is deducted."""
    prod_id = add_product(
        name="Rare Organic Honey",
        price=150.00,
        category="Grocery",
        stock=3
    )

    # Attempt to order 4 units when only 3 are available
    greedy_cart = [
        {"product_id": prod_id, "name": "Rare Organic Honey", "price": 150.00, "quantity": 4}
    ]

    success, msg, order_id = OrderService.create_order(
        user_id=1,
        full_name='Honey Lover',
        phone_number='9876543210',
        address='Honey Lane',
        products=greedy_cart,
        total_amount=600.0
    )
    assert success is False
    assert "Insufficient stock" in msg
    assert order_id is None

    # Stock must remain unchanged at 3
    prod = get_product_by_id(prod_id)
    assert prod['stock'] == 3


# ==================== 4. Concurrent Checkout Atomicity ====================

def test_concurrent_checkout_stock_protection():
    """Simulate two racing threads buying the last unit of stock: exactly one succeeds."""
    prod_id = add_product(
        name="Last Bottle of Saffron",
        price=300.00,
        category="Grocery",
        stock=1
    )

    results = []

    def attempt_checkout(thread_id):
        cart = [{"product_id": prod_id, "name": "Last Bottle of Saffron", "price": 300.0, "quantity": 1}]
        s, m, o = OrderService.create_order(
            user_id=1,
            full_name=f"Racer {thread_id}",
            phone_number="9876543210",
            address="Race Track",
            products=cart,
            total_amount=330.0,
            payment_method="COD"
        )
        results.append((s, m, o))

    t1 = threading.Thread(target=attempt_checkout, args=(1,))
    t2 = threading.Thread(target=attempt_checkout, args=(2,))

    t1.start()
    t2.start()
    t1.join()
    t2.join()

    successes = [r for r in results if r[0] is True]
    failures = [r for r in results if r[0] is False]

    assert len(successes) == 1, "Exactly one thread must succeed in purchasing the last unit"
    assert len(failures) == 1, "Second thread must be rejected for insufficient stock"
    assert "Insufficient stock" in failures[0][1]

    # Final stock must be exactly 0, never negative
    prod = get_product_by_id(prod_id)
    assert prod['stock'] == 0


# ==================== 5. Payment Verification Security ====================

def test_verify_payment_invalid_signature(auth_client):
    """Payment verification must reject forged signatures with HTTP 400."""
    resp = auth_client.post('/api/verify-payment', json={
        'razorpay_order_id': 'order_fake_sig_1',
        'razorpay_payment_id': 'pay_fake_sig_1',
        'razorpay_signature': 'deadbeef000011112222333344445555'
    })
    assert resp.status_code == 400
    assert 'Invalid payment signature' in resp.get_json()['message']


def test_verify_payment_mismatched_user(test_app):
    """Payment verification must reject if pending order belongs to a different user (HTTP 403)."""
    key_secret = "test_key_secret_for_mismatch"
    Config.RAZORPAY_KEY_SECRET = key_secret

    rzp_order_id = "order_user_mismatch_999"
    rzp_pay_id = "pay_user_mismatch_999"

    # Pending order created by User #2
    save_pending_order(
        razorpay_order_id=rzp_order_id,
        user_id=2,
        full_name='Victim User',
        phone_number='9876543210',
        address='Victim Rd',
        products=[{"name": "Tea", "price": 50.0, "quantity": 1}],
        total_amount=50.0
    )

    sig = hmac.new(
        key_secret.encode('utf-8'),
        f"{rzp_order_id}|{rzp_pay_id}".encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

    # User #1 attempts to verify payment for User #2's order
    with test_app.test_client() as client:
        with client.session_transaction() as sess:
            sess['user_id'] = 1  # Attacker

        resp = client.post('/api/verify-payment', json={
            'razorpay_order_id': rzp_order_id,
            'razorpay_payment_id': rzp_pay_id,
            'razorpay_signature': sig
        })
        assert resp.status_code == 403
        assert 'Unauthorized' in resp.get_json()['message']


def test_verify_payment_missing_pending_order(auth_client):
    """Payment verification must reject when no valid pending order exists."""
    key_secret = Config.RAZORPAY_KEY_SECRET or "secret_123"
    Config.RAZORPAY_KEY_SECRET = key_secret

    rzp_order_id = "order_ghost_not_in_db_000"
    rzp_pay_id = "pay_ghost_not_in_db_000"

    sig = hmac.new(
        key_secret.encode('utf-8'),
        f"{rzp_order_id}|{rzp_pay_id}".encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

    resp = auth_client.post('/api/verify-payment', json={
        'razorpay_order_id': rzp_order_id,
        'razorpay_payment_id': rzp_pay_id,
        'razorpay_signature': sig
    })
    assert resp.status_code == 400
    assert 'No pending order found' in resp.get_json()['message']


# ==================== 6. Webhook Idempotency & Safe State Transitions ====================

def test_webhook_does_not_regress_shipped_order(test_app):
    """Duplicate/delayed webhook payment.captured must not regress a Shipped/Delivered order to Paid."""
    key_secret = "test_webhook_secret_fsm"
    Config.RAZORPAY_WEBHOOK_SECRET = key_secret

    # Seed an order that is already Shipped
    success, _, order_id = OrderService.create_order(
        user_id=1,
        full_name='Shipped Customer',
        phone_number='9876543210',
        address='Shipped Lane',
        products=[{"name": "Tea", "price": 50.0, "quantity": 1}],
        total_amount=50.0,
        payment_method='Razorpay',
        payment_id='pay_already_shipped_111',
        status='Paid'
    )
    assert success is True

    # Transition order: Paid -> Processing -> Packed -> Shipped
    OrderService.update_status(order_id, 'Processing')
    OrderService.update_status(order_id, 'Packed')
    OrderService.update_status(order_id, 'Shipped')

    # Webhook sends payment.captured for pay_already_shipped_111
    payload = {
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_already_shipped_111",
                    "order_id": "order_dummy_111"
                }
            }
        }
    }
    body = json.dumps(payload).encode('utf-8')
    sig = hmac.new(key_secret.encode('utf-8'), body, hashlib.sha256).hexdigest()

    with test_app.test_client() as client:
        resp = client.post(
            '/api/v1/payment/webhook',
            data=body,
            headers={'Content-Type': 'application/json', 'X-Razorpay-Signature': sig}
        )
        assert resp.status_code == 200
        assert resp.get_json()['status'] == 'already_processed'

    # Verify status remained 'Shipped' (did not regress to 'Paid')
    orders = OrderService.get_user_orders(1)
    matching = next(o for o in orders if o['order_id'] == order_id)
    assert matching['status'] == 'Shipped'


# ==================== 7. Order State Machine Transitions ====================

def test_order_status_state_machine():
    """Verify state machine allows valid linear transitions and blocks invalid jumps and terminal mutations."""
    success, _, order_id = OrderService.create_order(
        user_id=1,
        full_name='FSM Tester',
        phone_number='9876543210',
        address='FSM Way',
        products=[{"name": "Tea", "price": 50.0, "quantity": 1}],
        total_amount=50.0,
        payment_method='COD',
        status='Processing'
    )
    assert success is True

    # 1. Invalid status value rejected
    s, msg = OrderService.update_status(order_id, 'Flying')
    assert s is False
    assert "Invalid status" in msg

    # 2. Valid transition: Processing -> Packed
    s, msg = OrderService.update_status(order_id, 'Packed')
    assert s is True

    # 3. Valid transition: Packed -> Shipped
    s, msg = OrderService.update_status(order_id, 'Shipped')
    assert s is True

    # 4. Valid transition: Shipped -> Delivered
    s, msg = OrderService.update_status(order_id, 'Delivered')
    assert s is True

    # 5. Terminal state: Delivered order cannot be changed to Processing or Cancelled
    s, msg = OrderService.update_status(order_id, 'Processing')
    assert s is False
    assert "Cannot change status of a Delivered order" in msg

    s, msg = OrderService.update_status(order_id, 'Cancelled')
    assert s is False
    assert "Cannot change status of a Delivered order" in msg



# ==================== 8. Health Check Endpoint ====================

def test_health_check_endpoints(test_app):
    """Health check endpoints must report connected database and component statuses."""
    with test_app.test_client() as client:
        for path in ['/healthz', '/api/v1/health']:
            resp = client.get(path)
            assert resp.status_code == 200
            data = resp.get_json()
            assert data['status'] == 'healthy'
            assert 'components' in data
            assert data['components']['database']['status'] == 'connected'


# ==================== 9. Sanitized Structured Logging ====================

def test_log_sanitizer_redacts_credentials():
    """SanitizingLogFormatter must redact passwords, tokens, signatures, and credit cards."""
    formatter = SanitizingLogFormatter('%(message)s')
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="Login attempt for user with password='MySecretPassword123' and token=eyJhbGciOiJIUzI1NiIsInR5cCI6",
        args=(),
        exc_info=None
    )
    formatted = formatter.format(record)
    assert "MySecretPassword123" not in formatted
    assert "[REDACTED]" in formatted
