"""
Products blueprint handling catalog listings, categories, and product query APIs.
"""
import logging
from flask import Blueprint, render_template, request, jsonify
from services.product_service import ProductService

logger = logging.getLogger(__name__)

products_bp = Blueprint('products', __name__)


CATEGORY_DEFINITIONS = {
    'vegetables': {
        'slug': 'vegetables',
        'title': 'Vegetables and Fruits',
        'heading': 'Vegetables & Fruits',
        'db_name': 'Fruits & Vegetables',
        'placeholder': 'Search vegetables & fruits...',
        'subcategories': [
            {'slug': 'all', 'name': 'All Products'},
            {'slug': 'vegetables', 'name': 'Vegetables'},
            {'slug': 'fruits', 'name': 'Fruits'},
            {'slug': 'exotics', 'name': 'Exotics'},
            {'slug': 'leafy', 'name': 'Leafy Greens'},
            {'slug': 'melons', 'name': 'Melons'},
        ]
    },
    'grocery': {
        'slug': 'grocery',
        'title': 'Premium Grocery Shop',
        'heading': 'Premium Grocery Shop',
        'db_name': 'Grocery',
        'placeholder': 'Search groceries...',
        'subcategories': [
            {'slug': 'all', 'name': 'All Products'},
            {'slug': 'atta', 'name': 'Atta'},
            {'slug': 'toor chana', 'name': 'Toor and chana'},
            {'slug': 'besan maida powder', 'name': 'Besan and Maida'},
            {'slug': 'rice', 'name': 'Rice'},
        ]
    },
    'baby_care': {
        'slug': 'baby_care',
        'title': 'Baby Care',
        'heading': 'Baby Care',
        'db_name': 'Baby Care',
        'placeholder': 'Search baby care...',
        'subcategories': [
            {'slug': 'all', 'name': 'All Products'},
            {'slug': 'daipers', 'name': 'Diapers'},
            {'slug': 'baby food', 'name': 'Baby Food'},
            {'slug': 'hair care', 'name': 'Hair Care'},
            {'slug': 'hygiene', 'name': 'Hygiene'},
        ]
    },
    'beverages': {
        'slug': 'beverages',
        'title': 'Beverages',
        'heading': 'Beverages',
        'db_name': 'Beverages',
        'placeholder': 'Search beverages...',
        'subcategories': [
            {'slug': 'all', 'name': 'All Beverages'},
            {'slug': 'soft drinks', 'name': 'Soft Drinks'},
            {'slug': 'lassi', 'name': 'Lassi'},
            {'slug': 'dairy', 'name': 'Dairy Drinks'},
            {'slug': 'energy bars', 'name': 'Energy Drinks'},
        ]
    },
    'dairy_breakfast': {
        'slug': 'dairy_breakfast',
        'title': 'Dairy and Breakfast',
        'heading': 'Dairy & Breakfast',
        'db_name': 'Dairy & Breakfast',
        'placeholder': 'Search dairy & breakfast...',
        'subcategories': [
            {'slug': 'all', 'name': 'All Products'},
            {'slug': 'milk', 'name': 'Milk'},
            {'slug': 'dairy', 'name': 'Dairy'},
            {'slug': 'breakfast', 'name': 'Breakfast'},
            {'slug': 'chocos', 'name': 'Chocos'},
        ]
    },
    'frozen_foods': {
        'slug': 'frozen_foods',
        'title': 'Frozen Foods',
        'heading': 'Frozen Foods',
        'db_name': 'Frozen Foods',
        'placeholder': 'Search frozen foods...',
        'subcategories': [
            {'slug': 'all', 'name': 'All Frozen Foods'},
            {'slug': 'ice cream', 'name': 'Ice Cream & Desserts'},
        ]
    },
    'home_kitchen': {
        'slug': 'home_kitchen',
        'title': 'Home and Kitchen',
        'heading': 'Home & Kitchen',
        'db_name': 'Home & Kitchen',
        'placeholder': 'Search home & kitchen...',
        'subcategories': [
            {'slug': 'all', 'name': 'All Products'},
            {'slug': 'pooja needs', 'name': 'Pooja Needs'},
            {'slug': 'dainning needs', 'name': 'Dainning Needs'},
            {'slug': 'kitchen', 'name': 'Kitchen'},
        ]
    },
    'household_items': {
        'slug': 'household_items',
        'title': 'Household Items',
        'heading': 'Household Items',
        'db_name': 'Household',
        'placeholder': 'Search household items...',
        'subcategories': [
            {'slug': 'all', 'name': 'All Products'},
            {'slug': 'freshners', 'name': 'Freshners'},
            {'slug': 'toilet cleaner', 'name': 'Toilet Cleaner'},
            {'slug': 'cleaning tools', 'name': 'Cleaning Tools'},
            {'slug': 'bathroom essential', 'name': 'Bathroom Essential'},
        ]
    },
    'personal_care': {
        'slug': 'personal_care',
        'title': 'Personal Care',
        'heading': 'Personal Care',
        'db_name': 'Personal Care',
        'placeholder': 'Search personal care...',
        'subcategories': [
            {'slug': 'all', 'name': 'All Products'},
            {'slug': 'Facewash', 'name': 'Facewash'},
            {'slug': 'Femine care', 'name': 'Feminine Care'},
            {'slug': 'Hair Care', 'name': 'Hair Care'},
            {'slug': 'Sunscreen', 'name': 'Sunscreen'},
            {'slug': 'Deodrant', 'name': 'Deodorant'},
            {'slug': 'personal care', 'name': 'Daily Grooming'},
        ]
    },
    'snacks': {
        'slug': 'snacks',
        'title': 'Snacks',
        'heading': 'Snacks',
        'db_name': 'Snacks',
        'placeholder': 'Search snacks...',
        'subcategories': [
            {'slug': 'all', 'name': 'All Products'},
            {'slug': 'soft drinks', 'name': 'Soft Drinks'},
            {'slug': 'energy bars', 'name': 'Energy Bars'},
            {'slug': 'cookie', 'name': 'Cookie'},
            {'slug': 'chips', 'name': 'Chips'},
        ]
    }
}


def render_category_page(cat_key: str) -> str:
    """Helper to render a category page with unified category.html template."""
    cat_cfg = CATEGORY_DEFINITIONS.get(cat_key)
    if not cat_cfg:
        cat_cfg = {
            'slug': cat_key,
            'title': cat_key.replace('_', ' ').title(),
            'heading': cat_key.replace('_', ' ').title(),
            'db_name': cat_key.replace('_', ' ').title(),
            'placeholder': f"Search {cat_key.replace('_', ' ')}...",
            'subcategories': [{'slug': 'all', 'name': 'All Products'}]
        }
    products = ProductService.get_products_by_category(cat_cfg['db_name'])
    return render_template('category.html', category_config=cat_cfg, products=products)


@products_bp.route('/category/<string:category_slug>', endpoint='category_view')
def category_view(category_slug: str) -> str:
    """Dynamic category route rendering unified category page."""
    return render_category_page(category_slug.lower())


@products_bp.route('/vegetables', endpoint='vegetables')
def vegetables() -> str:
    """Display Vegetables category products."""
    return render_category_page('vegetables')


@products_bp.route('/grocery', endpoint='grocery')
def grocery() -> str:
    """Display Grocery category products."""
    return render_category_page('grocery')


@products_bp.route('/home_kitchen', endpoint='home_kitchen')
def home_kitchen() -> str:
    """Display Home & Kitchen category products."""
    return render_category_page('home_kitchen')


@products_bp.route('/baby_care', endpoint='baby_care')
def baby_care() -> str:
    """Display Baby Care category products."""
    return render_category_page('baby_care')


@products_bp.route('/household_items', endpoint='household_items')
def household_items() -> str:
    """Display Household Items category products."""
    return render_category_page('household_items')


@products_bp.route('/personal_care', endpoint='personal_care')
def personal_care() -> str:
    """Display Personal Care category products."""
    return render_category_page('personal_care')


@products_bp.route('/snacks', endpoint='snacks')
def snacks() -> str:
    """Display Snacks category products."""
    return render_category_page('snacks')


@products_bp.route('/dairy_breakfast', endpoint='dairy_breakfast')
def dairy_breakfast() -> str:
    """Display Dairy & Breakfast category products."""
    return render_category_page('dairy_breakfast')


@products_bp.route('/beverages', endpoint='beverages')
def beverages() -> str:
    """Display Beverages category products."""
    return render_category_page('beverages')


@products_bp.route('/frozen_foods', endpoint='frozen_foods')
def frozen_foods() -> str:
    """Display Frozen Foods category products."""
    return render_category_page('frozen_foods')


@products_bp.route('/api/v1/products/list', methods=['GET'], endpoint='api_list_products')
def api_list_products():
    """API endpoint to get list of products with optional category and search filters."""
    category = request.args.get('category')
    search = request.args.get('search', '').lower().strip()

    products = ProductService.get_products_by_category(category)
    if search:
        products = [p for p in products if search in p['name'].lower() or search in (p.get('description') or '').lower()]

    return jsonify({
        'success': True,
        'count': len(products),
        'products': products
    }), 200


@products_bp.route('/api/v1/products/search', methods=['GET'], endpoint='api_search_products')
def api_search_products():
    """Live autocomplete search API returning matched products with limit."""
    query = request.args.get('q', '').strip()
    limit = request.args.get('limit', 8)
    try:
        limit = min(int(limit), 20)
    except (TypeError, ValueError):
        limit = 8

    if not query:
        return jsonify({'success': True, 'count': 0, 'results': []}), 200

    results = ProductService.search_products(query, limit=limit)
    return jsonify({
        'success': True,
        'query': query,
        'count': len(results),
        'results': results
    }), 200

