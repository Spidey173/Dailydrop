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


def test_product_routes(client):
    # /categories redirects cleanly to home
    cat_res = client.get('/categories')
    assert cat_res.status_code in [200, 302]

    category_routes = [
        '/grocery', '/vegetables', '/dairy_breakfast', '/snacks',
        '/beverages', '/frozen_foods', '/household_items',
        '/home_kitchen', '/personal_care', '/baby_care'
    ]
    for route in category_routes:
        res = client.get(route)
        assert res.status_code == 200, f"Failed for category route: {route}"


def test_api_products_list(client):
    res = client.get('/api/v1/products/list')
    assert res.status_code == 200
    json_data = res.get_json()
    assert json_data['success'] is True
    assert json_data['count'] > 200


def test_api_products_search(client):
    res = client.get('/api/v1/products/search?q=milk')
    assert res.status_code == 200
    data = res.get_json()
    assert data['success'] is True
    assert data['count'] > 0
    assert any('milk' in r['name'].lower() for r in data['results'])


    # 2. Search with empty query
    res_empty = client.get('/api/v1/products/search?q=')
    assert res_empty.status_code == 200
    assert res_empty.get_json()['count'] == 0

    # 3. Search with limit parameter
    res_limit = client.get('/api/v1/products/search?q=a&limit=3')
    assert res_limit.status_code == 200
    assert len(res_limit.get_json()['results']) <= 3


def test_api_v1_products_paginated(client):
    """Verify GET /api/v1/products pagination and metadata."""
    res = client.get('/api/v1/products?page=1&per_page=12')
    assert res.status_code == 200
    data = res.get_json()
    assert data['success'] is True
    assert len(data['products']) == 12
    assert data['page'] == 1
    assert data['per_page'] == 12
    assert data['total'] > 200
    assert data['pages'] >= 17

    # Verify second page returns different slice
    res_p2 = client.get('/api/v1/products?page=2&per_page=12')
    assert res_p2.status_code == 200
    data_p2 = res_p2.get_json()
    assert len(data_p2['products']) == 12
    assert data_p2['page'] == 2
    assert data['products'][0]['product_id'] != data_p2['products'][0]['product_id']


def test_api_v1_products_filters(client):
    """Verify GET /api/v1/products category and search query filters."""
    # Filter by category
    res_cat = client.get('/api/v1/products?category=Grocery&per_page=50')
    assert res_cat.status_code == 200
    data_cat = res_cat.get_json()
    assert data_cat['success'] is True
    assert data_cat['total'] > 0
    for p in data_cat['products']:
        assert p['category'] == 'Grocery'

    # Filter by search
    res_search = client.get('/api/v1/products?search=milk')
    assert res_search.status_code == 200
    data_search = res_search.get_json()
    assert data_search['success'] is True
    assert data_search['total'] > 0
    assert any('milk' in (p.get('name') or '').lower() for p in data_search['products'])


def test_strict_product_id_resolution():
    """Verify CatalogValidationService rejects missing or unknown product IDs with 400-level error."""
    from services.catalog_validation_service import CatalogValidationService
    from database import get_db_connection

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # 1. Missing product_id
            valid, err, _, _, _ = CatalogValidationService.validate_and_resolve_cart(
                cur,
                [{"name": "Mysterious Floating Item", "price": 99.0, "quantity": 1}]
            )
            assert valid is False
            assert "missing product_id" in err or "not found in catalog" in err

            # 2. Unknown numeric product_id
            valid, err, _, _, _ = CatalogValidationService.validate_and_resolve_cart(
                cur,
                [{"product_id": 888888, "name": "Fake Product", "price": 99.0, "quantity": 1}]
            )
            assert valid is False
            assert "not found in catalog" in err


def test_products_api_returns_all_items_across_pages(client):
    """
    Verify creating >100 products and that the frontend-facing API
    (/api/v1/products) successfully returns all of them across multiple pages.
    """
    from repositories.product_repository import add_product, clear_product_cache

    created_ids = []
    # Create 105 distinct products in a dedicated category
    for i in range(1, 106):
        pid = add_product(
            name=f"Bulk Product {i}",
            price=10.0 + i,
            category="BulkTest",
            subcategory="Testing",
            stock=50
        )
        assert pid is not None
        created_ids.append(pid)

    clear_product_cache()

    # 1. Verify single request with per_page=500 returns all >100 products in one pass
    res_large = client.get('/api/v1/products?category=BulkTest&per_page=500')
    assert res_large.status_code == 200
    data_large = res_large.get_json()
    assert data_large['success'] is True
    assert data_large['total'] == 105
    assert len(data_large['products']) == 105
    assert data_large['pages'] == 1

    # 2. Verify frontend pagination loop across multiple pages (e.g. per_page=25, 5 pages)
    collected_products = []
    page = 1
    total_pages = 1
    while page <= total_pages:
        res_page = client.get(f'/api/v1/products?category=BulkTest&page={page}&per_page=25')
        assert res_page.status_code == 200
        page_data = res_page.get_json()
        assert page_data['success'] is True
        collected_products.extend(page_data['products'])
        total_pages = page_data['pages']
        page += 1

    assert len(collected_products) == 105
    collected_ids = {p['product_id'] for p in collected_products}
    assert collected_ids == set(created_ids)



