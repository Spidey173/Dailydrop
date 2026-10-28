import io
import pytest
from app import create_app
from services.product_service import ProductService
from database import get_db_connection

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

MINIMAL_PNG = (
    b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
    b'\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00'
    b'\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
)

MINIMAL_JPG = (
    b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xff\xdb\x00C\x00'
    b'\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19'
    b'\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.\' \",#\x1c\x1c(7),01444\x1f'
    b'\'9=82<.342\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f\x00'
    b'\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04'
    b'\x05\x06\x07\x08\t\n\x0b\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xbf\x00\xff\xd9'
)

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
    Verify that an admin product upload converts to a Base64 Data URL,
    persists permanently into PostgreSQL, and can be edited with full cloud permanence.
    """
    # 1. Create a dummy image in memory
    if HAS_PIL:
        img = Image.new('RGB', (400, 400), color=(16, 185, 129))
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0)
    else:
        img_byte_arr = io.BytesIO(MINIMAL_PNG)

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
    assert data_add['image_path'].startswith('data:image/')

    # 3. Direct verification in PostgreSQL
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT name, price, category, stock, image_path FROM products WHERE product_id = %s", (product_id,))
            row = cur.fetchone()
            assert row is not None
            assert row['name'] == 'Permanent Test Dragonfruit'
            assert float(row['price']) == 89.50
            assert row['stock'] == 45
            assert row['image_path'].startswith('data:image/')

    # 4. Edit product via Admin Edit API
    if HAS_PIL:
        new_img = Image.new('RGB', (300, 300), color=(59, 130, 246))
        new_img_bytes = io.BytesIO()
        new_img.save(new_img_bytes, format='JPEG')
        new_img_bytes.seek(0)
    else:
        new_img_bytes = io.BytesIO(MINIMAL_JPG)

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
            assert updated_row['image_path'].startswith('data:image/')

    # 6. Verify via ProductService query (cache invalidated and re-queried)
    prod = ProductService.get_product(product_id)
    assert prod is not None
    assert prod['name'] == 'Updated Golden Dragonfruit'
    assert float(prod['price']) == 105.00

    # 7. Clean up test product permanently from PostgreSQL
    res_del = admin_client.post(f'/api/v1/admin/products/{product_id}/delete')
    assert res_del.status_code == 200
    assert ProductService.get_product(product_id) is None
