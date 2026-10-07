"""
Blueprints package registering modular application routes and backwards-compatible endpoint aliases.
"""
from flask import Flask, url_for
from blueprints.auth import auth_bp
from blueprints.main import main_bp
from blueprints.products import products_bp
from blueprints.cart import cart_bp
from blueprints.admin import admin_bp

__all__ = ['auth_bp', 'main_bp', 'products_bp', 'cart_bp', 'admin_bp', 'register_blueprints']

# Mapping of legacy endpoint names without blueprint prefix to full blueprint endpoints
ENDPOINT_ALIASES = {
    # Auth
    'signup': 'auth.signup',
    'login': 'auth.login',
    'admin_login': 'auth.admin_login',
    'logout': 'auth.logout',
    # Main
    'intro': 'main.intro',
    'index': 'main.index',
    'dashboard': 'main.dashboard',
    'contact_us': 'main.contact_us',
    'privacy_policy_signup': 'main.privacy_policy_signup',
    'privacy_policy_login': 'main.privacy_policy_login',
    'privacy_policy_signup_home': 'main.privacy_policy_signup_home',
    'terms_login': 'main.terms_login',
    'terms_signup': 'main.terms_signup',
    'terms_signup_home': 'main.terms_signup_home',
    'faqs': 'main.faqs',
    'about_us': 'main.about_us',
    # Products
    'vegetables': 'products.vegetables',
    'grocery': 'products.grocery',
    'home_kitchen': 'products.home_kitchen',
    'baby_care': 'products.baby_care',
    'household_items': 'products.household_items',
    'personal_care': 'products.personal_care',
    'snacks': 'products.snacks',
    'dairy_breakfast': 'products.dairy_breakfast',
    'beverages': 'products.beverages',
    'frozen_foods': 'products.frozen_foods',
    'api_list_products': 'products.api_list_products',
    # Cart & Orders & Wishlist
    'cart': 'cart.cart',
    'payment': 'cart.payment',
    'place_order': 'cart.place_order',
    'orders': 'cart.orders',
    'wishlist': 'cart.wishlist',
    'api_create_order': 'cart.api_create_order',
    'api_verify_payment': 'cart.api_verify_payment',
    # Admin
    'admin_dashboard': 'admin.admin_dashboard',
    'admin_orders': 'admin.admin_orders',
    'admin_orders_page': 'admin.admin_orders_page',
    'admin_inquiries': 'admin.admin_inquiries',
    'admin_inquiries_page': 'admin.admin_inquiries_page',
    'inquiries': 'admin.inquiries',
    'api_admin_analytics': 'admin.api_admin_analytics',

    'api_update_order_status': 'admin.api_update_order_status',
    'api_update_product_price': 'admin.api_update_product_price',
    'api_update_product_stock': 'admin.api_update_product_stock',
    'api_add_product': 'admin.api_add_product',
    'api_delete_product': 'admin.api_delete_product',
}


def register_blueprints(app: Flask) -> None:
    """Register all application blueprints and setup URL resolution aliases."""
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(products_bp)
    app.register_blueprint(cart_bp)
    app.register_blueprint(admin_bp)

    # Custom Jinja url_for wrapper to support both prefixed and legacy non-prefixed endpoint names
    orig_url_for = url_for

    def compatible_url_for(endpoint, **values):
        resolved_endpoint = ENDPOINT_ALIASES.get(endpoint, endpoint)
        return orig_url_for(resolved_endpoint, **values)

    app.jinja_env.globals['url_for'] = compatible_url_for
