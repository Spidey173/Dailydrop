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
            {'slug': 'atta', 'name': 'Atta & Flours'},
            {'slug': 'dals', 'name': 'Dals & Pulses'},
            {'slug': 'rice', 'name': 'Rice & Grains'},
            {'slug': 'spices', 'name': 'Spices & Masalas'},
            {'slug': 'salt', 'name': 'Salt & Sugar'},
            {'slug': 'besan maida powder', 'name': 'Besan & Maida'},
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
            {'slug': 'daipers', 'name': 'Diapers & Wipes'},
            {'slug': 'baby food', 'name': 'Baby Food'},
            {'slug': 'hygiene', 'name': 'Baby Hygiene'},
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
            {'slug': 'lassi', 'name': 'Lassi & Yogurt'},
            {'slug': 'dairy', 'name': 'Dairy Drinks'},
            {'slug': 'energy bars', 'name': 'Energy & Juices'},
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
            {'slug': 'dairy', 'name': 'Dairy & Butter'},
            {'slug': 'milk', 'name': 'Milk'},
            {'slug': 'breakfast', 'name': 'Bread & Breakfast'},
            {'slug': 'chocos', 'name': 'Cereals & Chocos'},
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
            {'slug': 'kitchen', 'name': 'Kitchen Tools'},
            {'slug': 'dainning needs', 'name': 'Dining Essentials'},
            {'slug': 'pooja needs', 'name': 'Pooja Needs'},
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
            {'slug': 'freshners', 'name': 'Fresheners & Air Care'},
            {'slug': 'cleaning tools', 'name': 'Cleaning & Detergents'},
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
            {'slug': 'facewash', 'name': 'Facewash'},
            {'slug': 'hair care', 'name': 'Hair Care'},
            {'slug': 'sunscreen', 'name': 'Sunscreen'},
            {'slug': 'deodrant', 'name': 'Deodorant'},
            {'slug': 'femine care', 'name': 'Feminine Care'},
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
            {'slug': 'chips', 'name': 'Chips & Crisps'},
            {'slug': 'cookie', 'name': 'Biscuits & Cookies'},
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


ALL_AISLES_META = [
    {'slug': 'vegetables', 'url': '/vegetables', 'name': 'Fruits & Vegetables', 'icon': 'fa-apple-alt', 'image': '/static/image/vegetables.jpg', 'desc': 'Fresh farm fruits, crisp vegetables & organic greens'},
    {'slug': 'dairy_breakfast', 'url': '/dairy_breakfast', 'name': 'Dairy & Breakfast', 'icon': 'fa-egg', 'image': '/static/image/dairy.jpg', 'desc': 'Milk, cheese, butter, wholesome breakfast spreads & breads'},
    {'slug': 'snacks', 'url': '/snacks', 'name': 'Snacks & Munchies', 'icon': 'fa-cookie-bite', 'image': '/static/image/snaks.jpeg', 'desc': 'Chips, biscuits, chocolates, cookies & namkeen'},
    {'slug': 'grocery', 'url': '/grocery', 'name': 'Premium Grocery', 'icon': 'fa-shopping-basket', 'image': '/static/image/grocery.jpeg', 'desc': 'Atta, rice, aromatic spices, pulses & daily essentials'},
    {'slug': 'beverages', 'url': '/beverages', 'name': 'Beverages & Drinks', 'icon': 'fa-glass-whiskey', 'image': '/static/image/beverages.webp', 'desc': 'Juices, craft sodas, refreshing lassis & energy drinks'},
    {'slug': 'baby_care', 'url': '/baby_care', 'name': 'Baby Care', 'icon': 'fa-baby', 'image': '/static/image/babycare.jpeg', 'desc': 'Diapers, gentle wipes, organic baby food & lotions'},
    {'slug': 'personal_care', 'url': '/personal_care', 'name': 'Personal Care', 'icon': 'fa-spa', 'image': '/static/image/personalcare.jpeg', 'desc': 'Facewashes, soaps, shampoos, hair oils & grooming'},
    {'slug': 'household_items', 'url': '/household_items', 'name': 'Household Items', 'icon': 'fa-home', 'image': '/static/image/households.jpeg', 'desc': 'Cleaning supplies, detergents, dishwash & air fresheners'},
    {'slug': 'home_kitchen', 'url': '/home_kitchen', 'name': 'Home & Kitchen', 'icon': 'fa-utensils', 'image': '/static/image/kitchen.jpeg', 'desc': 'Cookware, dining essentials, storage containers & pooja needs'},
    {'slug': 'frozen_foods', 'url': '/frozen_foods', 'name': 'Frozen Foods', 'icon': 'fa-ice-cream', 'image': '/static/slider/frozen_foods.webp', 'desc': 'Gourmet ice creams, frozen treats & desserts'}
]


@products_bp.route('/categories', endpoint='categories')
def categories_directory() -> str:
    """Display comprehensive visual directory of all shopping aisles."""
    return render_template('categories.html', aisles=ALL_AISLES_META)


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

