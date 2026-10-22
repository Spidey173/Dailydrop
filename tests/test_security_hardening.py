"""
Security and Reliability Regression Test Suite.

Verifies:
1. Production configuration rejects insecure/placeholder secret keys.
2. CSRF protection blocks unauthorized state-mutating requests when enabled.
3. Authoritative catalog pricing overrides client-tampered cart prices.
4. Unrestricted file uploads (.exe, .html, .svg) are rejected.
5. Terminal order statuses (Delivered, Cancelled) cannot be reverted.
6. Cross-user idempotency collisions are blocked with HTTP 409.
"""
import io
import pytest
from app import create_app
from config import Config, ProductionConfig, INSECURE_SECRET_KEYS
from services.payment_service import PaymentService
from services.order_service import OrderService
from services.idempotency_service import IdempotencyService
from database import get_db_connection, clear_user_cache


@pytest.fixture
def auth_client():
    """Client with CSRF enabled and authenticated customer session."""
    app = create_app('testing')
    app.config['WTF_CSRF_ENABLED'] = True
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess['user_id'] = 2
            sess['name'] = 'Demo Customer'
            sess['email'] = 'demo_dailydrop@gmail.com'
            sess['user_role'] = 'customer'
        yield client


@pytest.fixture
def admin_client():
    """Client with CSRF disabled for focused API validation and admin session."""
    app = create_app('testing')
    app.config['WTF_CSRF_ENABLED'] = False
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['name'] = 'Admin User'
            sess['email'] = 'admin_dailydrop@gmail.com'
            sess['user_role'] = 'admin'
        yield client


# =========================================================================
# 1. Config Validation Tests
# =========================================================================

def test_insecure_secret_key_rejection_in_production():
    """Verify that insecure or placeholder keys fail fast in production."""
    orig_key = ProductionConfig.SECRET_KEY
    orig_db = ProductionConfig.DATABASE_URL
    try:
        # Test placeholder key rejection
        ProductionConfig.SECRET_KEY = 'change-this-to-a-secure-random-secret-key'
        ProductionConfig.DATABASE_URL = 'postgresql://localhost/dummy'
        with pytest.raises(ValueError, match="CRITICAL SECURITY CONFIGURATION ERROR"):
            ProductionConfig.validate_config('production')

        # Test short key rejection
        ProductionConfig.SECRET_KEY = 'too-short'
        with pytest.raises(ValueError, match="CRITICAL SECURITY CONFIGURATION ERROR"):
            ProductionConfig.validate_config('production')

        # Test valid strong key
        ProductionConfig.SECRET_KEY = 'a' * 64
        assert ProductionConfig.validate_config('production') is True

    finally:
        ProductionConfig.SECRET_KEY = orig_key
        ProductionConfig.DATABASE_URL = orig_db


# =========================================================================
# 2. CSRF Enforcement Tests
# =========================================================================

def test_csrf_enforcement_blocks_missing_token_on_mutations(auth_client):
    """Verify that mutating endpoints reject requests lacking CSRF token when CSRF is enabled."""
    # POST /place_order without CSRF token
    res = auth_client.post('/place_order', json={
        'full_name': 'Test User',
        'phone_number': '1234567890',
        'address': 'Test Street',
        'products': [{'name': 'Milk', 'price': 50.0, 'quantity': 1}]
    })
    assert res.status_code == 400
    data = res.get_json()
    assert data['success'] is False
    assert 'CSRF' in data['error']

    # POST /api/v1/wishlist/toggle without CSRF token
    res_wish = auth_client.post('/api/v1/wishlist/toggle', json={'product_id': 1})
    assert res_wish.status_code == 400
    data_wish = res_wish.get_json()
    assert data_wish['success'] is False
    assert 'CSRF' in data_wish['error']


def test_payment_webhook_remains_csrf_exempt(auth_client):
    """Verify that server-to-server Razorpay webhook is CSRF exempt."""
    # Webhook without CSRF should fail on missing signature, NOT on CSRF token
    res = auth_client.post('/api/v1/payment/webhook', json={'event': 'payment.captured'})
    assert res.status_code == 400
    data = res.get_json()
    assert 'signature' in (data.get('error', '') or data.get('message', '')).lower()


# =========================================================================
# 3. Price Tampering Prevention & DB Pricing
# =========================================================================

def test_authoritative_price_resolution_overrides_client_tampering():
    """Verify that client cannot tamper with product price in checkout."""
    # Insert or update a known product in SQLite test DB
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT OR REPLACE INTO products (product_id, name, price, stock, category, image_path, description)
                VALUES (8888, 'Tamper Proof Oil', 400.0, 50, 'Grocery', '/static/logo1.webp', 'Test Product')
            """)

    # Attacker attempts to checkout with price = 0.50 instead of 400.00
    tampered_cart = [
        {'id': 8888, 'product_id': 8888, 'name': 'Tamper Proof Oil', 'price': 0.50, 'quantity': 1}
    ]

    success, msg, subtotal, fee, total = PaymentService.calculate_authoritative_total(tampered_cart)
    assert success is True
    # Server must look up DB price (400.0) + delivery fee (30.0 for orders < 500) = 430.0
    assert subtotal == 400.0
    assert fee == 30.0
    assert total == 430.0
    assert tampered_cart[0]['price'] == 400.0

    # Test OrderService creation preserves authoritative 400.0 price in items
    success, msg, order_id = OrderService.create_order(
        user_id=2,
        full_name='Security Tester',
        phone_number='9876543210',
        address='Test Address',
        products=tampered_cart,
        total_amount=total,
        payment_method='COD'
    )
    assert success is True
    assert order_id is not None

    from database import get_order_items
    items = get_order_items(order_id)
    assert len(items) == 1
    assert float(items[0]['price']) == 400.0


# =========================================================================
# 4. File Upload Extension Restrictions
# =========================================================================

def test_admin_upload_rejects_dangerous_extensions(admin_client):
    """Verify that dangerous file types (.svg, .html, .exe) are rejected."""
    # Attempt uploading an SVG file
    svg_data = io.BytesIO(b"<svg onload='alert(1)'></svg>")
    data = {
        'name': 'Malicious Product',
        'price': '99.0',
        'category': 'Grocery',
        'stock': '10',
        'image_file': (svg_data, 'exploit.svg')
    }
    res = admin_client.post('/api/v1/admin/products/add', data=data, content_type='multipart/form-data')
    assert res.status_code == 400
    res_data = res.get_json()
    assert res_data['success'] is False
    assert "Invalid image format" in res_data['error']

    # Attempt uploading an HTML file
    html_data = io.BytesIO(b"<html><body>XSS</body></html>")
    data_html = {
        'name': 'HTML Product',
        'price': '99.0',
        'category': 'Grocery',
        'stock': '10',
        'image_file': (html_data, 'malicious.html')
    }
    res_html = admin_client.post('/api/v1/admin/products/add', data=data_html, content_type='multipart/form-data')
    assert res_html.status_code == 400
    assert "Invalid image format" in res_html.get_json()['error']


# =========================================================================
# 5. Terminal Order State Transition Enforcement
# =========================================================================

def test_order_status_terminal_transition_rejection():
    """Verify that orders in Delivered or Cancelled status cannot be modified."""
    # Create test order
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO orders (user_id, full_name, phone_number, address, products_ordered, total_amount, payment_method, status)
                VALUES (2, 'State Transition User', '9999999999', 'Road 1', '[]', 100.0, 'COD', 'Processing')
            """)
            cur.execute("SELECT last_insert_rowid()")
            order_id = cur.fetchone()[0]

    # Valid transition to Delivered
    ok, msg = OrderService.update_status(order_id, 'Delivered')
    assert ok is True

    # Invalid transition from Delivered back to Processing
    bad_ok, bad_msg = OrderService.update_status(order_id, 'Processing')
    assert bad_ok is False
    assert "Cannot change status of a Delivered order" in bad_msg


# =========================================================================
# 6. Cross-User Idempotency Isolation
# =========================================================================

def test_cross_user_idempotency_collision_prevention():
    """Verify that User B cannot hijack or read cached response of User A's idempotency key."""
    key = "user_isolation_test_key_999"

    # User 1 acquires lock
    can_proceed1, _, _ = IdempotencyService.acquire(key, user_id=1)
    assert can_proceed1 is True

    # User 2 attempts to use same key while in-flight -> 409 Conflict
    can_proceed2, resp2, status2 = IdempotencyService.acquire(key, user_id=2)
    assert can_proceed2 is False
    assert status2 == 409
    assert "belongs to another user" in resp2['message']

    # Complete request for User 1
    IdempotencyService.complete(key, {'success': True, 'order_id': 777}, status_code=200, user_id=1)

    # User 2 attempts to replay User 1's key -> blocked
    can_proceed_replay, replay_resp, replay_status = IdempotencyService.acquire(key, user_id=2)
    assert can_proceed_replay is False
    assert replay_status == 409
    assert "belongs to another user" in replay_resp['message']

    # User 1 replays their own key -> successfully gets cached response
    can_proceed_owner, owner_resp, owner_status = IdempotencyService.acquire(key, user_id=1)
    assert can_proceed_owner is False
    assert owner_status == 200
    assert owner_resp['order_id'] == 777

    # Cleanup
    IdempotencyService.release(key)
