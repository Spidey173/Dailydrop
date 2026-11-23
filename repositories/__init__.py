"""
Data Access Repositories for Daily Drop.
Modularized persistence layer separating domain queries from connection pooling.
"""
from .user_repository import (
    get_user_by_email,
    get_user_by_id,
    clear_user_cache
)
from .product_repository import (
    get_all_products,
    get_product_by_id,
    get_product_by_name,
    get_products_paginated,
    add_product,
    update_product,
    update_product_price,
    update_product_stock,
    delete_product,
    get_low_stock_products,
    normalize_category,
    is_matching_category,
    clear_product_cache
)
from .order_repository import (
    get_all_orders_with_user_info,
    update_order_status,
    get_order_items,
    save_pending_order,
    get_pending_order,
    delete_pending_order
)
from .analytics_repository import (
    get_unified_analytics,
    get_dashboard_stats,
    get_sales_data,
    get_customer_audiences,
    get_category_revenue,
    get_hourly_order_distribution,
    clear_analytics_cache,
    _get_fallback_rfm_customers
)

__all__ = [
    'get_user_by_email',
    'get_user_by_id',
    'clear_user_cache',
    'get_all_products',
    'get_product_by_id',
    'get_product_by_name',
    'get_products_paginated',
    'add_product',
    'update_product',
    'update_product_price',
    'update_product_stock',
    'delete_product',
    'get_low_stock_products',
    'normalize_category',
    'is_matching_category',
    'clear_product_cache',
    'get_all_orders_with_user_info',
    'update_order_status',
    'get_order_items',
    'save_pending_order',
    'get_pending_order',
    'delete_pending_order',
    'get_unified_analytics',
    'get_dashboard_stats',
    'get_sales_data',
    'get_customer_audiences',
    'get_category_revenue',
    'get_hourly_order_distribution',
    'clear_analytics_cache',
    '_get_fallback_rfm_customers'
]

