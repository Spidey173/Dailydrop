import json
import pytest
from app import create_app
from database import (
    get_db_connection, get_all_products, get_user_by_email,
    get_dashboard_stats
)

@pytest.fixture
def client():
    test_app = create_app('testing')
    test_app.config['WTF_CSRF_ENABLED'] = False
    with test_app.test_client() as client:
        yield client

def test_home_page(client):
    response = client.get('/')
    assert response.status_code == 200

def test_products_seeded():
    products = get_all_products()
    assert len(products) > 200


def test_admin_account_exists():
    admin = get_user_by_email('admin_dailydrop@gmail.com')
    assert admin is not None
    assert admin['role'] == 'admin'


def test_dashboard_stats_endpoint():
    stats = get_dashboard_stats()
    assert 'total_orders' in stats
    assert 'total_users' in stats
    assert 'total_products' in stats

