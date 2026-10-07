"""
Unit and integration tests for Admin Blueprint, permissions, and management APIs.
"""
import pytest
from app import create_app
from services.product_service import ProductService
from services.order_service import OrderService


@pytest.fixture
def admin_client():
    app = create_app('testing')
    app.config['WTF_CSRF_ENABLED'] = False
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['name'] = 'Admin User'
            sess['email'] = 'admin_dailydrop@gmail.com'
            sess['user_role'] = 'admin'
        yield client


@pytest.fixture
def unauthorized_client():
    app = create_app('testing')
    app.config['WTF_CSRF_ENABLED'] = False
    with app.test_client() as client:
        yield client


def test_admin_dashboard_access(admin_client, unauthorized_client):
    # Admin allowed
    res_admin = admin_client.get('/admin/dashboard')
    assert res_admin.status_code == 200

    # Non-admin redirected
    res_unauth = unauthorized_client.get('/admin/dashboard', follow_redirects=False)
    assert res_unauth.status_code == 302


def test_admin_analytics_api(admin_client, unauthorized_client):
    # Admin allowed
    res = admin_client.get('/api/v1/admin/analytics')
    assert res.status_code == 200
    data = res.get_json()
    assert data['success'] is True
    assert 'stats' in data
    assert 'sales_info' in data

    # Unauthorized receives 401
    unauth_res = unauthorized_client.get('/api/v1/admin/analytics')
    assert unauth_res.status_code == 401


def test_admin_product_management(admin_client):
    # 1. Add product
    add_res = admin_client.post('/api/v1/admin/products/add', data={
        'name': 'Test Integration Product',
        'price': '19.99',
        'category': 'Grocery',
        'stock': '40'
    })
    assert add_res.status_code == 201
    prod_data = add_res.get_json()
    assert prod_data['success'] is True
    prod_id = prod_data['product_id']

    # 2. Update price
    price_res = admin_client.post(f'/api/v1/admin/products/{prod_id}/price', json={'price': 24.99})
    assert price_res.status_code == 200
    assert price_res.get_json()['new_price'] == 24.99

    # 3. Update stock
    stock_res = admin_client.post(f'/api/v1/admin/products/{prod_id}/stock', json={'stock': 65})
    assert stock_res.status_code == 200
    assert stock_res.get_json()['new_stock'] == 65

    # 4. Delete product
    del_res = admin_client.delete(f'/api/v1/admin/products/{prod_id}/delete')
    assert del_res.status_code == 200
    assert del_res.get_json()['success'] is True
