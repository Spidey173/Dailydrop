"""
Unit and integration tests for Wishlist feature and WishlistService.
"""
import pytest
from app import create_app
from services.auth_service import AuthService
from services.wishlist_service import WishlistService
from database import get_db_connection, clear_user_cache


@pytest.fixture
def app_instance():
    app = create_app('testing')
    app.config['WTF_CSRF_ENABLED'] = False
    return app


import uuid

@pytest.fixture
def test_user():
    email = f'wishlist_tester_{uuid.uuid4().hex[:8]}@example.com'
    success, msg, user_id = AuthService.register_user('Wishlist Tester', email, 'Password@1234')
    assert success is True and user_id is not None, f"Failed to setup test user: {msg}"
    yield user_id

    # Cleanup
    if user_id:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM wishlist WHERE user_id = %s", (user_id,))
                cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
        clear_user_cache(email, user_id)


def test_wishlist_service_operations(test_user):
    product_id = 1

    # 1. Initially empty
    assert WishlistService.get_wishlist_count(test_user) == 0
    assert len(WishlistService.get_user_wishlist_ids(test_user)) == 0

    # 2. Toggle to add
    success, msg, in_wishlist, count = WishlistService.toggle_item(test_user, product_id)
    assert success is True
    assert in_wishlist is True
    assert count == 1

    # 3. Retrieve wishlist
    items = WishlistService.get_user_wishlist(test_user)
    assert len(items) == 1
    assert items[0]['product_id'] == product_id

    # 4. Toggle to remove
    success2, msg2, in_wishlist2, count2 = WishlistService.toggle_item(test_user, product_id)
    assert success2 is True
    assert in_wishlist2 is False
    assert count2 == 0

    # 5. Add and explicit remove
    WishlistService.toggle_item(test_user, product_id)
    assert WishlistService.get_wishlist_count(test_user) == 1
    rem_success, rem_msg, rem_count = WishlistService.remove_item(test_user, product_id)
    assert rem_success is True
    assert rem_count == 0


def test_guest_wishlist_redirect(app_instance):
    client = app_instance.test_client()
    guest_res = client.get('/wishlist')
    assert guest_res.status_code == 302
    assert '/login' in guest_res.headers['Location']


def test_authenticated_wishlist_endpoints(app_instance, test_user):
    client = app_instance.test_client()
    with client.session_transaction() as sess:
        sess['user_id'] = test_user
        sess['name'] = 'Wishlist Tester'
        sess['email'] = 'wishlist_tester@example.com'
        sess['user_role'] = 'customer'

    # 1. Logged in user access to /wishlist
    auth_res = client.get('/wishlist')
    assert auth_res.status_code == 200

    # 2. Toggle item via API
    toggle_res = client.post('/api/v1/wishlist/toggle', json={'product_id': 1})
    assert toggle_res.status_code == 200
    toggle_data = toggle_res.get_json()
    assert toggle_data['success'] is True
    assert toggle_data['in_wishlist'] is True

    # 3. Fetch IDs
    ids_res = client.get('/api/v1/wishlist/ids')
    assert ids_res.status_code == 200
    ids_data = ids_res.get_json()
    assert ids_data['success'] is True
    assert 1 in ids_data['ids']

    # 4. Remove item via API
    remove_res = client.post('/api/v1/wishlist/remove', json={'product_id': 1})
    assert remove_res.status_code == 200
    remove_data = remove_res.get_json()
    assert remove_data['success'] is True
    assert remove_data['count'] == 0
