"""
Admin blueprint managing dashboard analytics, customer order management, and product catalog controls.
"""
import os
import logging
from datetime import datetime
from flask import Blueprint, render_template, request, jsonify, current_app
from werkzeug.utils import secure_filename

from services.product_service import ProductService
from services.order_service import OrderService
from services.contact_service import ContactService
from blueprints.helpers import admin_required
from utils import sanitize_string
from database import normalize_category, clear_product_cache

logger = logging.getLogger(__name__)

admin_bp = Blueprint('admin', __name__)


@admin_bp.route('/admin', endpoint='admin_root')
@admin_bp.route('/admin/dashboard', endpoint='admin_dashboard')
@admin_required
def admin_dashboard():
    """Render the Admin Portal dashboard with sub-millisecond in-memory cache responses."""
    analytics = OrderService.get_analytics(days=30)
    products = ProductService.get_products_by_category()
    low_stock = ProductService.get_low_stock(threshold=10)
    contact_messages = ContactService.get_all_messages()

    return render_template(
        'admin_dashboard.html',
        stats=analytics.get('stats', {}),
        products=products,
        low_stock=low_stock,
        sales_info=analytics.get('sales', {}),
        contact_messages=contact_messages,
        category_revenue=analytics.get('categories', {}),
        hourly_distribution=analytics.get('hourly', {})
    )



@admin_bp.route('/api/v1/admin/messages/<int:message_id>/delete', methods=['POST', 'DELETE'], endpoint='api_delete_message')
@admin_required
def api_delete_message(message_id: int):
    """API endpoint to delete or dismiss a customer contact message."""
    success, message = ContactService.delete_message(message_id)
    if success:
        return jsonify({'success': True, 'message': message, 'message_id': message_id}), 200
    return jsonify({'success': False, 'error': message}), 400



@admin_bp.route('/api/v1/admin/analytics', methods=['GET'], endpoint='api_admin_analytics')
@admin_required
def api_admin_analytics():
    """API endpoint serving live analytics metrics for dynamic charts."""
    analytics = OrderService.get_analytics(days=30)
    low_stock = ProductService.get_low_stock(threshold=10)
    critical_stock = ProductService.get_low_stock(threshold=5)

    return jsonify({
        'success': True,
        'stats': analytics.get('stats', {}),
        'sales_info': analytics.get('sales', {}),
        'category_revenue': analytics.get('categories', {}),
        'hourly_distribution': analytics.get('hourly', {}),
        'low_stock_count': len(low_stock),
        'critical_stock_count': len(critical_stock)
    }), 200


@admin_bp.route('/admin/orders', endpoint='admin_orders_page')
@admin_bp.route('/admin_orders', endpoint='admin_orders')
@admin_required
def admin_orders():
    """Render dedicated Customer Orders Management page for Admin."""
    analytics = OrderService.get_analytics(days=30)
    all_orders = OrderService.get_all_orders()
    return render_template(
        'admin_orders.html',
        stats=analytics.get('stats', {}),
        all_orders=all_orders
    )


@admin_bp.route('/admin/inquiries', endpoint='admin_inquiries_page')
@admin_bp.route('/admin_inquiries', endpoint='admin_inquiries')
@admin_bp.route('/inquiries', endpoint='inquiries')
@admin_required
def admin_inquiries():
    """Render dedicated Customer Contact Inquiries page for Admin."""
    contact_messages = ContactService.get_all_messages()
    return render_template(
        'admin_inquiries.html',
        contact_messages=contact_messages
    )



@admin_bp.route('/api/v1/admin/orders/<int:order_id>/status', methods=['POST', 'PATCH'], endpoint='api_update_order_status')
@admin_required
def api_update_order_status(order_id: int):
    """API to update a customer order delivery status."""
    data = request.get_json(silent=True) or request.form
    new_status = sanitize_string(data.get('status', 'Processing'))
    if not new_status:
        return jsonify({'success': False, 'error': 'Status is required'}), 400

    success, message = OrderService.update_status(order_id, new_status)
    if success:
        return jsonify({
            'success': True,
            'message': message,
            'order_id': order_id,
            'new_status': new_status
        }), 200
    return jsonify({'success': False, 'error': message}), 400


@admin_bp.route('/api/v1/admin/products/<int:product_id>/price', methods=['POST', 'PATCH'], endpoint='api_update_product_price')
@admin_required
def api_update_product_price(product_id: int):
    """API to update a product price dynamically via inline AJAX."""
    data = request.get_json(silent=True) or request.form
    try:
        new_price = float(data.get('price', 0))
    except (ValueError, TypeError):
        return jsonify({'success': False, 'error': 'Invalid price format'}), 400

    success, message = ProductService.update_price(product_id, new_price)
    if success:
        return jsonify({
            'success': True,
            'message': f'Price updated to ${new_price:.2f}',
            'product_id': product_id,
            'new_price': new_price
        }), 200
    return jsonify({'success': False, 'error': message}), 400


@admin_bp.route('/api/v1/admin/products/<int:product_id>/stock', methods=['POST', 'PATCH'], endpoint='api_update_product_stock')
@admin_required
def api_update_product_stock(product_id: int):
    """API to update product stock quantity via inline AJAX."""
    data = request.get_json(silent=True) or request.form
    try:
        new_stock = int(data.get('stock', 0))
    except (ValueError, TypeError):
        return jsonify({'success': False, 'error': 'Invalid stock number'}), 400

    success, message = ProductService.update_stock(product_id, new_stock)
    if success:
        return jsonify({
            'success': True,
            'message': f'Stock updated to {new_stock} units',
            'product_id': product_id,
            'new_stock': new_stock
        }), 200
    return jsonify({'success': False, 'error': message}), 400


import io
import base64

def process_and_persist_image(file_storage) -> str:
    """
    Process an uploaded image file, optimize and downsample it for web delivery,
    and convert to a compact Base64 Data URL (WebP) for permanent storage
    in PostgreSQL that persists across all environments, deployments, and restarts.
    Also saves a local backup copy in static/uploads if running locally.
    """
    if not file_storage or not getattr(file_storage, 'filename', None):
        return ""

    raw_filename = file_storage.filename
    ext = os.path.splitext(raw_filename)[1].lower()
    allowed_exts = current_app.config.get('ALLOWED_IMAGE_EXTENSIONS', {'.png', '.jpg', '.jpeg', '.webp'})
    if ext not in allowed_exts:
        raise ValueError(f"Invalid image format '{ext}'. Allowed formats: {', '.join(sorted(allowed_exts))}")

    try:
        file_bytes = file_storage.read()
        if not file_bytes:
            return ""

        # Try optimizing with PIL if installed
        try:
            from PIL import Image, ImageOps
            img = Image.open(io.BytesIO(file_bytes))
            img = ImageOps.exif_transpose(img)

            # Downsample to max 600x600 for optimal product display
            img.thumbnail((600, 600), Image.Resampling.LANCZOS)

            buffer = io.BytesIO()
            if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
                img.save(buffer, format='WEBP', quality=82, method=6)
            else:
                img = img.convert('RGB')
                img.save(buffer, format='WEBP', quality=82, method=6)

            compressed_bytes = buffer.getvalue()
            b64_str = base64.b64encode(compressed_bytes).decode('utf-8')
            data_url = f"data:image/webp;base64,{b64_str}"
        except ImportError:
            # Safe fallback if Pillow is not installed in the runtime environment
            b64_str = base64.b64encode(file_bytes).decode('utf-8')
            mime = 'image/jpeg' if ext in ('.jpg', '.jpeg') else f'image/{ext.lstrip(".")}'
            data_url = f"data:{mime};base64,{b64_str}"
            compressed_bytes = file_bytes

        # If on local disk and uploads permitted, also save a local backup copy
        if not current_app.config.get('DISABLE_FILE_UPLOADS', False) and os.getenv('VERCEL') != '1':
            try:
                clean_base = secure_filename(os.path.splitext(raw_filename)[0]) or 'uploaded_image'
                timestamp = int(datetime.now().timestamp())
                filename = f"{timestamp}_{clean_base}.webp" if data_url.startswith("data:image/webp") else f"{timestamp}_{clean_base}{ext}"
                uploads_dir = os.path.join(current_app.static_folder or 'static', 'uploads')
                os.makedirs(uploads_dir, exist_ok=True)
                with open(os.path.join(uploads_dir, filename), 'wb') as f:
                    f.write(compressed_bytes)
            except Exception as backup_err:
                logger.warning(f"Could not save local disk backup: {backup_err}")

        return data_url
    except Exception as e:
        logger.error(f"Image processing error: {e}. Falling back to raw base64 encode.")
        try:
            file_storage.seek(0)
            raw_b64 = base64.b64encode(file_storage.read()).decode('utf-8')
            mime = 'image/jpeg' if ext in ('.jpg', '.jpeg') else f'image/{ext.lstrip(".")}'
            return f"data:{mime};base64,{raw_b64}"
        except Exception as fallback_err:
            logger.error(f"Fallback base64 encode error: {fallback_err}")
            raise


@admin_bp.route('/api/v1/admin/products/add', methods=['POST'], endpoint='api_add_product')
@admin_required
def api_add_product():
    """API to create a new product in the catalog with permanent cloud database persistence."""
    data = request.form if request.form else (request.get_json(silent=True) or {})
    try:
        name = sanitize_string(data.get('name', ''))
        price = float(data.get('price', 0))
        raw_category = sanitize_string(data.get('category', 'Grocery'))
        category = normalize_category(raw_category)
        subcategory = sanitize_string(data.get('subcategory', ''))
        stock = int(data.get('stock', 50))
        image_path = sanitize_string(data.get('image_path', ''))

        # If subcategory is empty, intelligently infer it for Produce
        if not subcategory and category == 'Fruits & Vegetables':
            name_lower = name.lower()
            if any(f in name_lower for f in ('apple', 'banana', 'melon', 'fruit', 'mango', 'orange', 'grape', 'berry', 'watermelon', 'pineapple')):
                subcategory = 'fruits'
            else:
                subcategory = 'vegetables'

        if 'image_file' in request.files:
            file = request.files['image_file']
            if file and file.filename:
                image_path = process_and_persist_image(file)

        if not image_path:
            cat_lower = category.lower()
            if 'veg' in cat_lower or 'fruit' in cat_lower:
                image_path = '/static/fruits-vegetables/pineapple.jpeg' if 'pineapple' in name.lower() else '/static/fruits-vegetables/apples.jpeg'
            else:
                image_path = '/static/product-placeholder.svg'

        success, message, new_id = ProductService.create_product(
            name=name, price=price, category=category,
            subcategory=subcategory, image_path=image_path,
            description='', stock=stock
        )

        if success:
            clear_product_cache(new_id)
            return jsonify({
                'success': True,
                'message': message,
                'product_id': new_id,
                'category': category,
                'subcategory': subcategory,
                'image_path': image_path
            }), 201
        return jsonify({'success': False, 'error': message}), 400
    except ValueError as ve:
        return jsonify({'success': False, 'error': str(ve)}), 400
    except Exception as e:
        logger.error(f"Error adding product: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/api/v1/admin/products/<int:product_id>/edit', methods=['POST', 'PUT'], endpoint='api_edit_product')
@admin_required
def api_edit_product(product_id: int):
    """API to update an existing product with permanent cloud database persistence."""
    data = request.form if request.form else (request.get_json(silent=True) or {})
    try:
        kwargs = {}
        if 'name' in data and data.get('name'):
            kwargs['name'] = sanitize_string(data.get('name'))
        if 'price' in data and data.get('price') != '':
            kwargs['price'] = float(data.get('price'))
        if 'category' in data and data.get('category'):
            kwargs['category'] = normalize_category(sanitize_string(data.get('category')))
        if 'subcategory' in data:
            kwargs['subcategory'] = sanitize_string(data.get('subcategory'))
        if 'stock' in data and data.get('stock') != '':
            kwargs['stock'] = int(data.get('stock'))
        if 'description' in data:
            kwargs['description'] = sanitize_string(data.get('description'))

        # Check if a new image was uploaded
        if 'image_file' in request.files:
            file = request.files['image_file']
            if file and file.filename:
                kwargs['image_path'] = process_and_persist_image(file)
        elif 'image_path' in data and data.get('image_path'):
            kwargs['image_path'] = sanitize_string(data.get('image_path'))

        success, message = ProductService.update_product(product_id, **kwargs)
        if success:
            clear_product_cache(product_id)
            return jsonify({
                'success': True,
                'message': f'Product #{product_id} updated permanently in database',
                'product_id': product_id,
                'updated_fields': list(kwargs.keys())
            }), 200
        return jsonify({'success': False, 'error': message}), 400
    except ValueError as ve:
        return jsonify({'success': False, 'error': str(ve)}), 400
    except Exception as e:
        logger.error(f"Error editing product #{product_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/api/v1/admin/products/<int:product_id>/delete', methods=['POST', 'DELETE'], endpoint='api_delete_product')
@admin_required
def api_delete_product(product_id: int):
    """API to delete a product by ID."""
    success, message = ProductService.remove_product(product_id)
    if success:
        return jsonify({'success': True, 'message': message, 'product_id': product_id}), 200
    return jsonify({'success': False, 'error': message}), 404
