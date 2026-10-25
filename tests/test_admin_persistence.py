import io
import pytest
from PIL import Image
from app import create_app
from services.product_service import ProductService
from database import get_db_connection

@pytest.fixture
def admin_client():
    """Client with CSRF disabled for admin persistence testing."""
    app = create_app('testing')
    app.config['WTF_CSRF_ENABLED'] = False
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['name'] = 'Admin User'
            sess['email'] = 'admin_dailydrop@gmail.com'
            sess['user_role'] = 'admin'
        yield client

def test_admin_upload_and_edit_permanent_persistence(admin_client):
    """
    Verify that an admin product upload converts to an optimized Base64 WebP Data URL,
    persists permanently into PostgreSQL, and can be edited with full cloud permanence.
    """
    # 1. Create a dummy image in memory
    img = Image.new('RGB', (400, 400), color=(16, 185, 129))
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PNG')
    img_byte_arr.seek(0)

    # 2. Add product via Admin API
    add_payload = {
        'name': 'Permanent Test Dragonfruit',
        'price': '89.50',
        'category': 'Fruits & Vegetables',
        'subcategory': 'fruits',
        'stock': '45',
        'image_file': (img_byte_arr, 'test_dragonfruit.png')
    }
    res_add = admin_client.post('/api/v1/admin/products/add', data=add_payload, content_type='multipart/form-data')
    assert res_add.status_code == 201
    data_add = res_add.get_json()
    assert data_add['success'] is True
    product_id = data_add['product_id']
    assert product_id is not None
    assert data_add['image_path'].startswith('data:image/webp;base64,')

    # 3. Direct verification in PostgreSQL
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT name, price, category, stock, image_path FROM products WHERE product_id = %s", (product_id,))
            row = cur.fetchone()
            assert row is not None
            assert row['name'] == 'Permanent Test Dragonfruit'
            assert float(row['price']) == 89.50
            assert row['stock'] == 45
            assert row['image_path'].startswith('data:image/webp;base64,')

    # 4. Edit product via Admin Edit API
    new_img = Image.new('RGB', (300, 300), color=(59, 130, 246))
    new_img_bytes = io.BytesIO()
    new_img.save(new_img_bytes, format='JPEG')
    new_img_bytes.seek(0)

    edit_payload = {
        'name': 'Updated Golden Dragonfruit',
        'price': '105.00',
        'category': 'Fruits & Vegetables',
        'subcategory': 'exotic',
        'stock': '60',
        'image_file': (new_img_bytes, 'golden_dragonfruit.jpg')
    }
    res_edit = admin_client.post(f'/api/v1/admin/products/{product_id}/edit', data=edit_payload, content_type='multipart/form-data')
    assert res_edit.status_code == 200
    data_edit = res_edit.get_json()
    assert data_edit['success'] is True

    # 5. Direct verification in PostgreSQL after edit
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT name, price, subcategory, stock, image_path FROM products WHERE product_id = %s", (product_id,))
            updated_row = cur.fetchone()
            assert updated_row['name'] == 'Updated Golden Dragonfruit'
            assert float(updated_row['price']) == 105.00
            assert updated_row['subcategory'] == 'exotic'
            assert updated_row['stock'] == 60
            assert updated_row['image_path'].startswith('data:image/webp;base64,')

    # 6. Verify via ProductService query (cache invalidated and re-queried)
    prod = ProductService.get_product(product_id)
    assert prod is not None
    assert prod['name'] == 'Updated Golden Dragonfruit'
    assert float(prod['price']) == 105.00

    # 7. Clean up test product permanently from PostgreSQL
    res_del = admin_client.post(f'/api/v1/admin/products/{product_id}/delete')
    assert res_del.status_code == 200
    assert ProductService.get_product(product_id) is None
