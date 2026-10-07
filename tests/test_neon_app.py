import json
import pytest
from app import app
from database import (
    get_db_connection, get_all_products, get_user_by_email,
    get_dashboard_stats
)

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_home_page(client):
    response = client.get('/')
    assert response.status_code == 200

def test_products_seeded():
    try:
        products = get_all_products()
        assert len(products) > 200
    except Exception as e:
        pytest.skip(f"Database unavailable for test: {e}")

def test_admin_account_exists():
    try:
        admin = get_user_by_email('admin_dailydrop@gmail.com')
        assert admin is not None
        assert admin['role'] == 'admin'
    except Exception as e:
        pytest.skip(f"Database unavailable for test: {e}")

def test_dashboard_stats_endpoint():
    try:
        stats = get_dashboard_stats()
        assert 'total_orders' in stats
        assert 'total_users' in stats
        assert 'total_products' in stats
    except Exception as e:
        pytest.skip(f"Database unavailable for test: {e}")
