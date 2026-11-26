"""
Unit and integration tests for Authentication Blueprint & AuthService.
"""
import pytest
from app import create_app
from services.auth_service import AuthService
from core.database import get_db_connection
from repositories.user_repository import clear_user_cache
from werkzeug.security import check_password_hash


@pytest.fixture
def client():
    app = create_app('testing')
    app.config['WTF_CSRF_ENABLED'] = False  # Disable CSRF in tests for clean endpoint testing
    with app.test_client() as client:
        yield client


def test_customer_registration_and_login(client):
    test_email = 'bp_test_customer@example.com'
    test_password = 'ValidPassword@123'
    test_name = 'Blueprint Test Customer'

    # Cleanup if exists
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM users WHERE email = %s", (test_email,))
    clear_user_cache(test_email)

    # 1. Test registration via AuthService
    success, msg, user_id = AuthService.register_user(test_name, test_email, test_password)
    assert success is True
    assert user_id is not None

    # 2. Test password is saved as hash
    user = AuthService.get_user_by_id(user_id)
    assert user is not None
    assert user['email'] == test_email
    assert check_password_hash(user['password'], test_password)

    # 3. Test duplicate registration prevention
    dup_success, dup_msg, _ = AuthService.register_user(test_name, test_email, test_password)
    assert dup_success is False
    assert 'already registered' in dup_msg.lower()

    # 4. Test authentication with valid credentials
    auth_success, auth_msg, auth_user = AuthService.authenticate_user(test_email, test_password)
    assert auth_success is True
    assert auth_user['id'] == user_id

    # 5. Test authentication with invalid password
    bad_success, bad_msg, _ = AuthService.authenticate_user(test_email, 'WrongPassword@999')
    assert bad_success is False

    # 6. Test login via HTTP route
    res = client.post('/login', data={'email': test_email, 'password': test_password}, follow_redirects=True)
    assert res.status_code == 200

    # 7. Cleanup
    if user_id:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
        clear_user_cache(test_email, user_id)


def test_admin_authentication():
    # Test valid admin login
    success, msg, admin_user = AuthService.authenticate_admin('admin_dailydrop@gmail.com', 'Dailydrop@173')
    assert success is True
    assert admin_user is not None
    assert admin_user['role'] == 'admin'

    # Test invalid admin login
    bad_success, _, _ = AuthService.authenticate_admin('admin_dailydrop@gmail.com', 'IncorrectAdminPass')
    assert bad_success is False


def test_admin_block_on_customer_signup():
    success, msg, _ = AuthService.register_user('Fake Admin', 'new_admin@dailydrop.com', 'AdminPass@123')
    assert success is False
    assert 'admin' in msg.lower()


def test_demo_customer_authentication():
    # Test valid demo customer authentication
    success, msg, demo_user = AuthService.authenticate_user('demo_dailydrop@gmail.com', 'Demouser@123')
    assert success is True
    assert demo_user is not None
    assert demo_user['email'] == 'demo_dailydrop@gmail.com'
    assert demo_user['role'] == 'customer'


def test_logout_redirects_to_intro(client):
    res = client.get('/logout', follow_redirects=False)
    assert res.status_code == 302
    assert res.headers['Location'] == '/'


def test_signup_and_login_session_persistence_dev_http():
    """
    Regression Test: Ensure that in dev-like config over plain http,
    signing up, logging in, and accessing protected pages preserves session cookies
    without redirecting back to the login page.
    """
    app = create_app('testing')
    app.config['WTF_CSRF_ENABLED'] = False
    app.config['SESSION_COOKIE_SECURE'] = False
    client = app.test_client()

    email = 'dev_persist_user@example.com'
    password = 'Password@123'
    name = 'Dev Persist User'

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM users WHERE email = %s", (email,))
    clear_user_cache(email)

    try:
        # 1. Signup with follow_redirects
        signup_res = client.post('/signup', data={
            'name': name,
            'email': email,
            'password': password
        }, base_url='http://localhost:5000', follow_redirects=True)
        assert signup_res.status_code == 200

        # 2. Login with follow_redirects
        login_res = client.post('/login', data={
            'email': email,
            'password': password
        }, base_url='http://localhost:5000', follow_redirects=True)
        assert login_res.status_code == 200

        # 3. Access protected page /orders
        orders_res = client.get('/orders', base_url='http://localhost:5000', follow_redirects=True)
        assert orders_res.status_code == 200
        # Must NOT be redirected to /login
        assert 'login' not in orders_res.headers.get('Location', '').lower()
        with client.session_transaction() as sess:
            assert sess.get('user_id') is not None
            assert sess.get('email') == email
    finally:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM users WHERE email = %s", (email,))
        clear_user_cache(email)


def test_signup_and_login_session_persistence_prod_https():
    """
    Regression Test: Ensure that in production-like config over HTTPS (Vercel),
    signing up, logging in, and accessing protected pages preserves secure session cookies
    without redirecting back to the login page.
    """
    app = create_app('testing')
    app.config['WTF_CSRF_ENABLED'] = False
    app.config['SESSION_COOKIE_SECURE'] = True
    app.config['ENV'] = 'production'
    client = app.test_client()

    email = 'prod_persist_user@example.com'
    password = 'Password@123'
    name = 'Prod Persist User'

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM users WHERE email = %s", (email,))
    clear_user_cache(email)

    try:
        # 1. Signup with follow_redirects over HTTPS
        signup_res = client.post('/signup', data={
            'name': name,
            'email': email,
            'password': password
        }, base_url='https://dailydrop18.vercel.app', follow_redirects=True)
        assert signup_res.status_code == 200

        # 2. Login with follow_redirects over HTTPS
        login_res = client.post('/login', data={
            'email': email,
            'password': password
        }, base_url='https://dailydrop18.vercel.app', follow_redirects=True)
        assert login_res.status_code == 200

        # 3. Access protected page /orders over HTTPS
        orders_res = client.get('/orders', base_url='https://dailydrop18.vercel.app', follow_redirects=True)
        assert orders_res.status_code == 200
        # Must NOT be redirected to /login
        assert 'login' not in orders_res.headers.get('Location', '').lower()
        assert b'orders' in orders_res.data.lower()
        with client.session_transaction(base_url='https://dailydrop18.vercel.app') as sess:
            assert sess.get('user_id') is not None
            assert sess.get('email') == email
    finally:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM users WHERE email = %s", (email,))
        clear_user_cache(email)


