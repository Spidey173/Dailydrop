"""
Admin blueprint managing dashboard analytics, customer order management, and product catalog controls.
"""
import os
import logging
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from werkzeug.utils import secure_filename

from services.product_service import ProductService
from services.order_service import OrderService
from services.contact_service import ContactService
from blueprints.helpers import admin_required
from utils import sanitize_string
from extensions import csrf

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
@csrf.exempt
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
@csrf.exempt
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
@csrf.exempt
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
@csrf.exempt
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


@admin_bp.route('/api/v1/admin/products/add', methods=['POST'], endpoint='api_add_product')
@csrf.exempt
@admin_required
def api_add_product():
    """API to create a new product in the catalog with image upload support."""
    data = request.form if request.form else (request.get_json(silent=True) or {})
    try:
        name = sanitize_string(data.get('name', ''))
        price = float(data.get('price', 0))
        category = sanitize_string(data.get('category', 'Grocery'))
        stock = int(data.get('stock', 50))
        image_path = sanitize_string(data.get('image_path', ''))

        if 'image_file' in request.files:
            file = request.files['image_file']
            if file and file.filename:
                raw_filename = file.filename
                ext = os.path.splitext(raw_filename)[1].lower() or '.png'
                clean_base = secure_filename(os.path.splitext(raw_filename)[0]) or 'uploaded_image'
                timestamp = int(datetime.now().timestamp())
                filename = f"{timestamp}_{clean_base}{ext}"

                uploads_dir = os.path.join(current_app.static_folder, 'uploads')
                os.makedirs(uploads_dir, exist_ok=True)
                save_path = os.path.join(uploads_dir, filename)
                file.save(save_path)
                image_path = f'/static/uploads/{filename}'

        if not image_path:
            image_path = '/static/logo.webp'

        success, message, new_id = ProductService.create_product(
            name=name, price=price, category=category,
            subcategory='', image_path=image_path,
            description='', stock=stock
        )

        if success:
            return jsonify({
                'success': True,
                'message': message,
                'product_id': new_id,
                'image_path': image_path
            }), 201
        return jsonify({'success': False, 'error': message}), 400
    except Exception as e:
        logger.error(f"Error adding product: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/api/v1/admin/products/<int:product_id>/delete', methods=['POST', 'DELETE'], endpoint='api_delete_product')
@csrf.exempt
@admin_required
def api_delete_product(product_id: int):
    """API to delete a product by ID."""
    success, message = ProductService.remove_product(product_id)
    if success:
        return jsonify({'success': True, 'message': message, 'product_id': product_id}), 200
    return jsonify({'success': False, 'error': message}), 404
