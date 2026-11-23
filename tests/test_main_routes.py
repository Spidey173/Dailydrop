"""
Unit and integration tests for Main Blueprint, static informational views, and contact messages.
"""
import pytest
from app import create_app
from services.contact_service import ContactService
from database import get_db_connection


@pytest.fixture
def client():
    app = create_app('testing')
    app.config['WTF_CSRF_ENABLED'] = False
    with app.test_client() as client:
        yield client


def test_public_pages(client):
    public_endpoints = [
        '/', '/index', '/about_us', '/faqs',
        '/privacy_policy_signup', '/privacy_policy_login',
        '/privacy_policy_signup_home', '/terms_login',
        '/terms_signup', '/terms_signup_home'
    ]
    for ep in public_endpoints:
        res = client.get(ep)
        assert res.status_code == 200, f"Failed for public endpoint: {ep}"


def test_contact_service_submission():
    name = 'Feedback User'
    email = 'feedback_test@example.com'
    subject = 'General Feedback'
    message = 'Love the quick delivery and fresh groceries!'

    success, msg, msg_id = ContactService.submit_message(
        user_id=None,
        name=name,
        email=email,
        phone='9876543210',
        subject=subject,
        message=message
    )
    assert success is True
    assert msg_id is not None

    # Cleanup message
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM contact_messages WHERE id = %s", (msg_id,))


def test_verification_endpoints(client):
    """
    Verify core application endpoints required for production verification:
    /healthz, /, /api/v1/products, and /admin/login.
    """
    # 1. /healthz
    res_health = client.get('/healthz')
    assert res_health.status_code == 200
    health_data = res_health.get_json()
    assert health_data['status'] == 'healthy'
    assert 'database' in health_data['components']
    assert 'redis' in health_data['components']

    # 2. Storefront root /
    res_root = client.get('/')
    assert res_root.status_code == 200
    assert b'DailyDrop' in res_root.data or b'Daily Drop' in res_root.data

    # 3. GET /api/v1/products
    res_products = client.get('/api/v1/products?per_page=12')
    assert res_products.status_code == 200
    prods_data = res_products.get_json()
    assert prods_data['success'] is True
    assert len(prods_data['products']) == 12
    assert prods_data['total'] > 100

    # 4. Admin login page /admin/login (and /admin_login)
    for path in ['/admin/login', '/admin_login']:
        res_admin = client.get(path)
        assert res_admin.status_code == 200
        assert b'Admin' in res_admin.data


def test_root_route_authenticated_vs_guest(client):
    """
    Ensure root / displays intro to guests, but renders the storefront for logged-in customers
    and redirects admins to the admin dashboard.
    """
    # 1. Guest -> intro page
    res_guest = client.get('/')
    assert res_guest.status_code == 200
    assert b'Everything You Need' in res_guest.data
    assert b'Shop Now' in res_guest.data

    # 2. Customer logged in -> storefront index.html
    with client.session_transaction() as sess:
        sess['user_id'] = 1
        sess['user_role'] = 'customer'
        sess['name'] = 'Customer One'
        sess['email'] = 'customer@example.com'

    res_customer = client.get('/')
    assert res_customer.status_code == 200
    # Storefront should display categories and products, not intro hero
    assert b'Explore by Category' in res_customer.data or b'Shop by Category' in res_customer.data or b'DailyDrop' in res_customer.data
    assert b'Everything You Need' not in res_customer.data

    # 3. /index, /store, /shop should also render storefront directly
    for path in ['/index', '/store', '/shop']:
        res_store = client.get(path)
        assert res_store.status_code == 200
        assert b'DailyDrop' in res_store.data

    # 4. Admin logged in -> redirects to admin_dashboard
    with client.session_transaction() as sess:
        sess['user_id'] = 2
        sess['user_role'] = 'admin'
        sess['name'] = 'Admin One'
        sess['email'] = 'admin@example.com'

    res_admin = client.get('/')
    assert res_admin.status_code == 302
    assert '/admin/dashboard' in res_admin.headers['Location']


