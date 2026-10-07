"""
Unit and integration tests for Razorpay PaymentService and payment endpoints.
"""
import hmac
import hashlib
import pytest
from app import create_app
from services.payment_service import PaymentService
from config import Config


def test_payment_authoritative_calculation_free_delivery():
    """Test order above Rs. 500 gets free delivery (fee = 0)."""
    items = [
        {"name": "Basmati Rice 5kg", "price": 450.0, "quantity": 1},
        {"name": "Olive Oil 1L", "price": 600.0, "quantity": 1}
    ]
    success, msg, subtotal, fee, total = PaymentService.calculate_authoritative_total(items)
    assert success is True
    assert subtotal == 1050.0
    assert fee == 0.0
    assert total == 1050.0


def test_payment_authoritative_calculation_with_delivery_fee():
    """Test order below Rs. 500 incurs Rs. 30 delivery fee."""
    items = [
        {"name": "Organic Apples 1kg", "price": 120.0, "quantity": 2}
    ]
    success, msg, subtotal, fee, total = PaymentService.calculate_authoritative_total(items)
    assert success is True
    assert subtotal == 240.0
    assert fee == 30.0
    assert total == 270.0


def test_payment_authoritative_calculation_invalid():
    """Test empty cart or negative price is rejected."""
    success, msg, _, _, _ = PaymentService.calculate_authoritative_total([])
    assert success is False

    bad_items = [{"name": "Fake Item", "price": -50.0, "quantity": 1}]
    success, msg, _, _, _ = PaymentService.calculate_authoritative_total(bad_items)
    assert success is False


def test_payment_signature_verification():
    """Test HMAC SHA256 cryptographic signature validation."""
    key_secret = Config.RAZORPAY_KEY_SECRET or "mock_test_key_secret_123"
    Config.RAZORPAY_KEY_SECRET = key_secret
    order_id = "order_test_99999"
    payment_id = "pay_test_88888"

    # Compute valid signature
    msg = f"{order_id}|{payment_id}".encode("utf-8")
    valid_sig = hmac.new(key_secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()

    assert PaymentService.verify_payment_signature(order_id, payment_id, valid_sig) is True
    assert PaymentService.verify_payment_signature(order_id, payment_id, "invalid_tampered_sig") is False


def test_payment_routes_require_login():
    """Test payment endpoints reject unauthenticated users."""
    app = create_app('testing')
    with app.test_client() as client:
        # GET /payment requires login
        resp = client.get('/payment')
        assert resp.status_code == 302
        assert '/login' in resp.headers.get('Location', '')

        # POST /api/v1/payment/create-order requires login
        resp = client.post('/api/v1/payment/create-order', json={})
        assert resp.status_code in [302, 401]

        # POST /api/v1/payment/verify requires login
        resp = client.post('/api/v1/payment/verify', json={})
        assert resp.status_code in [302, 401]


def test_api_create_order_minimum_amount():
    """Test /api/create-order rejects amounts under 100 paise (HTTP 400)."""
    app = create_app('testing')
    with app.test_client() as client:
        resp = client.post('/api/create-order', json={'amount': 50, 'currency': 'INR'})
        assert resp.status_code == 400
        data = resp.get_json()
        assert "100 paise" in (data.get('message', '') or data.get('error', ''))


def test_api_verify_payment_validation():
    """Test /api/verify-payment validates missing fields and bad signatures."""
    app = create_app('testing')
    key_secret = Config.RAZORPAY_KEY_SECRET or "test_secret_123"
    Config.RAZORPAY_KEY_SECRET = key_secret

    with app.test_client() as client:
        # 1. Missing fields should return 400
        resp = client.post('/api/verify-payment', json={'razorpay_order_id': 'order_123'})
        assert resp.status_code == 400
        assert 'Missing' in resp.get_json().get('message', '')

        # 2. Invalid signature mismatch should return 400
        resp = client.post('/api/verify-payment', json={
            'razorpay_order_id': 'order_123',
            'razorpay_payment_id': 'pay_123',
            'razorpay_signature': 'invalid_signature_hex'
        })
        assert resp.status_code == 400
        assert 'Invalid' in resp.get_json().get('message', '')

        # 3. Valid HMAC-SHA256 signature should return 200
        order_id = 'order_abc123'
        pay_id = 'pay_xyz789'
        valid_sig = hmac.new(
            key_secret.encode('utf-8'),
            f"{order_id}|{pay_id}".encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        resp = client.post('/api/verify-payment', json={
            'razorpay_order_id': order_id,
            'razorpay_payment_id': pay_id,
            'razorpay_signature': valid_sig
        })
        assert resp.status_code == 200
        assert resp.get_json().get('success') is True


def test_razorpay_webhook_signature_and_idempotency():
    """Verify /api/v1/payment/webhook validates HMAC signature and handles duplicate events idempotently."""
    import json
    app = create_app('testing')
    key_secret = "test_webhook_secret_key_456"
    Config.RAZORPAY_WEBHOOK_SECRET = key_secret
    Config.RAZORPAY_KEY_SECRET = key_secret

    with app.test_client() as client:
        payload = {
            "entity": "event",
            "event": "payment.captured",
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_test_idempotent_123",
                        "order_id": "order_test_idempotent_123",
                        "amount": 25000,
                        "status": "captured"
                    }
                }
            }
        }
        body_bytes = json.dumps(payload).encode('utf-8')

        # 1. Invalid signature should return 400
        bad_resp = client.post(
            '/api/v1/payment/webhook',
            data=body_bytes,
            headers={'Content-Type': 'application/json', 'X-Razorpay-Signature': 'invalid_signature_hex'}
        )
        assert bad_resp.status_code == 400
        assert 'Invalid' in bad_resp.get_json().get('error', '')

        # 2. Valid signature for an already fulfilled order should return 200 with already_processed
        valid_sig = hmac.new(key_secret.encode('utf-8'), body_bytes, hashlib.sha256).hexdigest()

        # Seed an order with payment_id = pay_test_idempotent_123
        from services.order_service import OrderService
        OrderService.create_order(
            user_id=1,
            full_name='Existing Customer',
            phone_number='9876543210',
            address='123 Main St',
            products=[{"name": "Tea", "price": 50.0, "quantity": 1}],
            total_amount=50.0,
            payment_method='Razorpay',
            payment_id='pay_test_idempotent_123',
            status='Paid'
        )

        resp = client.post(
            '/api/v1/payment/webhook',
            data=body_bytes,
            headers={'Content-Type': 'application/json', 'X-Razorpay-Signature': valid_sig}
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get('status') == 'already_processed'


def test_razorpay_webhook_client_disconnect_recovery():
    """Verify webhook recovers pending order and completes order placement if client disconnects."""
    import json
    from database import save_pending_order, get_pending_order
    from services.order_service import OrderService
    app = create_app('testing')
    key_secret = "test_webhook_recovery_secret_789"
    Config.RAZORPAY_WEBHOOK_SECRET = key_secret
    Config.RAZORPAY_KEY_SECRET = key_secret

    rzp_order_id = "order_disconnect_recovery_888"
    rzp_payment_id = "pay_disconnect_recovery_999"

    # Simulate pending order saved when client launched payment modal
    save_pending_order(
        razorpay_order_id=rzp_order_id,
        user_id=1,
        full_name='Disconnected Customer',
        phone_number='9123456780',
        address='456 Disconnect Rd',
        products=[{"name": "Brown Bread", "price": 40.0, "quantity": 2, "image": "/static/logo.webp"}],
        total_amount=80.0
    )
    assert get_pending_order(rzp_order_id) is not None

    with app.test_client() as client:
        webhook_payload = {
            "entity": "event",
            "event": "payment.captured",
            "payload": {
                "payment": {
                    "entity": {
                        "id": rzp_payment_id,
                        "order_id": rzp_order_id,
                        "amount": 8000,
                        "status": "captured"
                    }
                }
            }
        }
        body_bytes = json.dumps(webhook_payload).encode('utf-8')
        sig = hmac.new(key_secret.encode('utf-8'), body_bytes, hashlib.sha256).hexdigest()

        # Razorpay sends webhook
        resp = client.post(
            '/api/v1/payment/webhook',
            data=body_bytes,
            headers={'Content-Type': 'application/json', 'X-Razorpay-Signature': sig}
        )
        assert resp.status_code == 200
        res_data = resp.get_json()
        assert res_data.get('status') == 'order_recovered'
        recovered_order_id = res_data.get('order_id')
        assert recovered_order_id is not None

        # Verify pending order was cleaned up
        assert get_pending_order(rzp_order_id) is None

        # Verify recovered order in orders table
        user_orders = OrderService.get_user_orders(1)
        placed = next((o for o in user_orders if o['order_id'] == recovered_order_id), None)
        assert placed is not None
        assert placed['payment_id'] == rzp_payment_id
        assert placed['status'] == 'Paid'
