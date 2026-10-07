"""
Unit and integration tests for Cart & Orders Blueprint & OrderService.
"""
import pytest
import json
from app import create_app
from services.auth_service import AuthService
from services.order_service import OrderService
from database import get_db_connection, clear_user_cache


import uuid

@pytest.fixture
def test_user():
    email = f'cart_test_{uuid.uuid4().hex[:8]}@example.com'
    success, msg, user_id = AuthService.register_user('Cart Tester', email, 'Password@1234')
    assert success is True and user_id is not None, f"Failed to setup test user: {msg}"
    yield user_id

    # Cleanup
    if user_id:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM orders WHERE user_id = %s", (user_id,))
                cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
        clear_user_cache(email, user_id)


@pytest.fixture
def client(test_user):
    app = create_app('testing')
    app.config['WTF_CSRF_ENABLED'] = False
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess['user_id'] = test_user
            sess['name'] = 'Cart Tester'
            sess['email'] = 'cart_test_user@example.com'
            sess['user_role'] = 'customer'
        yield client


def test_cart_and_payment_views(client):
    res_cart = client.get('/cart')
    assert res_cart.status_code == 200

    res_payment = client.get('/payment')
    assert res_payment.status_code == 200


def test_order_creation_and_history(client, test_user):
    items = [
        {"name": "Organic Tomatoes", "price": 3.99, "quantity": 2},
        {"name": "Whole Milk", "price": 4.50, "quantity": 1}
    ]

    # 1. Place order via OrderService
    success, msg, order_id = OrderService.create_order(
        user_id=test_user,
        full_name='Cart Tester',
        phone_number='9876543210',
        address='789 Market Ave',
        products=items,
        total_amount=12.48
    )
    assert success is True
    assert order_id is not None

    # 2. Retrieve customer orders
    orders = OrderService.get_user_orders(test_user)
    assert len(orders) >= 1
    placed_order = next((o for o in orders if o['order_id'] == order_id), None)
    assert placed_order is not None
    assert len(placed_order['products']) == 2

    # 3. View orders page via HTTP
    res = client.get('/orders')
    assert res.status_code == 200


def test_place_order_endpoint(client):
    order_payload = {
        'full_name': 'Cart Tester',
        'phone_number': '1234567890',
        'address': '456 Test Blvd',
        'products': [{'name': 'Apple', 'price': 1.50, 'quantity': 3}],
        'total_amount': 4.50
    }
    res = client.post('/place_order', json=order_payload)
    assert res.status_code == 200
    res_json = res.get_json()
    assert res_json['success'] is True


def test_normalized_order_items(test_user):
    """Verify orders persist normalized relational rows into order_items table."""
    from database import get_order_items
    items = [
        {"name": "Organic Almonds 500g", "price": 12.50, "quantity": 2, "image": "/static/logo.webp"},
        {"name": "Fresh Avocados 2pk", "price": 6.00, "quantity": 1, "image": "/static/logo.webp"}
    ]
    success, msg, order_id = OrderService.create_order(
        user_id=test_user,
        full_name='Relational Tester',
        phone_number='9876543210',
        address='123 Relational Way',
        products=items,
        total_amount=31.00
    )
    assert success is True
    assert order_id is not None

    # Verify rows in normalized order_items table
    order_items = get_order_items(order_id)
    assert len(order_items) == 2
    assert order_items[0]['name'] == "Organic Almonds 500g"
    assert order_items[0]['quantity'] == 2
    assert order_items[0]['price'] == 12.50
    assert order_items[0]['subtotal'] == 25.00
    assert order_items[1]['name'] == "Fresh Avocados 2pk"
    assert order_items[1]['quantity'] == 1
    assert order_items[1]['price'] == 6.00
    assert order_items[1]['subtotal'] == 6.00

    # Verify OrderService.get_user_orders() loads directly from normalized order_items
    user_orders = OrderService.get_user_orders(test_user)
    matching = next(o for o in user_orders if o['order_id'] == order_id)
    assert len(matching['products']) == 2
    assert matching['products'][0]['name'] == "Organic Almonds 500g"


def test_atomic_inventory_decrement_and_race_prevention(test_user):
    """Verify UPDATE products SET stock = stock - %s WHERE stock >= %s atomically decrements and prevents overselling."""
    from database import add_product, get_product_by_id, delete_product

    # Create a product with initial stock of 10
    product_id = add_product(
        name="Limited Edition Olive Oil",
        price=20.00,
        category="Grocery",
        stock=10
    )
    assert product_id is not None

    try:
        # 1. Purchase 3 units -> stock becomes 7
        order_items = [{"product_id": product_id, "name": "Limited Edition Olive Oil", "price": 20.00, "quantity": 3}]
        success, msg, order_id = OrderService.create_order(
            user_id=test_user,
            full_name='Stock Tester',
            phone_number='9876543210',
            address='100 Inventory Lane',
            products=order_items,
            total_amount=60.00
        )
        assert success is True
        prod = get_product_by_id(product_id)
        assert prod['stock'] == 7

        # 2. Attempt to purchase 8 units (exceeds remaining stock 7) -> Rejected atomically
        greedy_items = [{"product_id": product_id, "name": "Limited Edition Olive Oil", "price": 20.00, "quantity": 8}]
        fail_success, fail_msg, fail_oid = OrderService.create_order(
            user_id=test_user,
            full_name='Greedy Buyer',
            phone_number='9876543210',
            address='100 Inventory Lane',
            products=greedy_items,
            total_amount=160.00
        )
        assert fail_success is False
        assert "Insufficient stock" in fail_msg
        assert fail_oid is None

        # Verify stock was preserved at 7 (transaction rolled back)
        prod_after = get_product_by_id(product_id)
        assert prod_after['stock'] == 7

        # 3. Duplicate items in cart aggregation: 4 + 4 = 8 units (exceeds 7) -> Rejected atomically
        dup_items = [
            {"product_id": product_id, "name": "Limited Edition Olive Oil", "price": 20.00, "quantity": 4},
            {"product_id": product_id, "name": "Limited Edition Olive Oil", "price": 20.00, "quantity": 4}
        ]
        dup_success, dup_msg, _ = OrderService.create_order(
            user_id=test_user,
            full_name='Duplicate Buyer',
            phone_number='9876543210',
            address='100 Inventory Lane',
            products=dup_items,
            total_amount=160.00
        )
        assert dup_success is False
        assert "Insufficient stock" in dup_msg
        assert get_product_by_id(product_id)['stock'] == 7

    finally:
        delete_product(product_id)
