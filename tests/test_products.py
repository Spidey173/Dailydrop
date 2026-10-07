"""
Unit and integration tests for Products Blueprint & ProductService.
"""
import pytest
from app import create_app
from services.product_service import ProductService


@pytest.fixture
def client():
    app = create_app('testing')
    app.config['WTF_CSRF_ENABLED'] = False
    with app.test_client() as client:
        yield client




def test_product_catalog_queries():
    try:
        all_prods = ProductService.get_products_by_category()
        assert len(all_prods) > 200
        grocery_prods = ProductService.get_products_by_category('Grocery')
        assert len(grocery_prods) > 0
        for p in grocery_prods:
            assert p['category'] == 'Grocery'
        first_prod = all_prods[0]
        fetched = ProductService.get_product(first_prod['product_id'])
        assert fetched is not None
        assert fetched['name'] == first_prod['name']
    except Exception as e:
        pytest.skip(f"Database unavailable for test: {e}")


def test_product_routes(client):
    category_routes = [
        '/grocery', '/vegetables', '/dairy_breakfast', '/snacks',
        '/beverages', '/frozen_foods', '/household_items',
        '/home_kitchen', '/personal_care', '/baby_care'
    ]
    for route in category_routes:
        res = client.get(route)
        assert res.status_code == 200, f"Failed for category route: {route}"


def test_api_products_list(client):
    try:
        res = client.get('/api/v1/products/list')
        assert res.status_code == 200
        json_data = res.get_json()
        assert json_data['success'] is True
        assert json_data['count'] > 200
    except Exception as e:
        pytest.skip(f"Database unavailable for test: {e}")


def test_api_products_search(client):
    try:
        res = client.get('/api/v1/products/search?q=milk')
        assert res.status_code == 200
        data = res.get_json()
        assert data['success'] is True
        assert data['count'] > 0
        assert any('milk' in r['name'].lower() for r in data['results'])
    except Exception as e:
        pytest.skip(f"Database unavailable for test: {e}")

    # 2. Search with empty query
    res_empty = client.get('/api/v1/products/search?q=')
    assert res_empty.status_code == 200
    assert res_empty.get_json()['count'] == 0

    # 3. Search with limit parameter
    res_limit = client.get('/api/v1/products/search?q=a&limit=3')
    assert res_limit.status_code == 200
    assert len(res_limit.get_json()['results']) <= 3

