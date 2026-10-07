"""
Unit and integration tests for Authentication Blueprint & AuthService.
"""
import pytest
from app import create_app
from services.auth_service import AuthService
from database import get_db_connection, clear_user_cache
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

