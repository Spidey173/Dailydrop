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

