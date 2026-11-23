"""
Product Data Repository.
Handles product catalog retrieval, filtering, updates, tiered caching, and stock modifications.
"""
import time
import logging
from typing import Any, Dict, List, Optional, Tuple
from psycopg2.extras import RealDictCursor
from database import get_db_connection, DatabaseError

logger = logging.getLogger("dailydrop.repositories.product")

_PRODUCT_CACHE: Dict[str, Tuple[float, List[Dict[str, Any]]]] = {}
_CACHE_TTL_SECONDS = 300.0  # 5 minutes in-memory cache for ultra-fast page loads

CATEGORY_CANONICAL_MAP = {
    'vegetables': 'Fruits & Vegetables',
    'fruits': 'Fruits & Vegetables',
    'fruits & vegetables': 'Fruits & Vegetables',
    'fruits and vegetables': 'Fruits & Vegetables',
    'fruits_vegetables': 'Fruits & Vegetables',
    'produce': 'Fruits & Vegetables',
    'fruit & vegetable': 'Fruits & Vegetables',

    'dairy': 'Dairy & Breakfast',
    'dairy & breakfast': 'Dairy & Breakfast',
    'dairy and breakfast': 'Dairy & Breakfast',
    'dairy_breakfast': 'Dairy & Breakfast',
    'breakfast': 'Dairy & Breakfast',

    'household': 'Household',
    'household items': 'Household',
    'household_items': 'Household',

    'home & kitchen': 'Home & Kitchen',
    'home and kitchen': 'Home & Kitchen',
    'home kitchen': 'Home & Kitchen',
    'home_kitchen': 'Home & Kitchen',
    'kitchen': 'Home & Kitchen',

    'baby care': 'Baby Care',
    'baby_care': 'Baby Care',

    'frozen foods': 'Frozen Foods',
    'frozen_foods': 'Frozen Foods',
    'frozen': 'Frozen Foods',

    'personal care': 'Personal Care',
    'personal_care': 'Personal Care',

    'grocery': 'Grocery',
    'groceries': 'Grocery',

    'beverages': 'Beverages',
    'drinks': 'Beverages',

    'snacks': 'Snacks',
}


def normalize_category(category: Optional[str]) -> str:
    """Normalize category name to standard canonical catalog name."""
    if not category:
        return 'Grocery'
    cleaned = category.strip()
    return CATEGORY_CANONICAL_MAP.get(cleaned.lower(), cleaned)


def is_matching_category(product_cat: Optional[str], target_cat: Optional[str]) -> bool:
    """Case-insensitive matching supporting category aliases & synonyms."""
    if not target_cat:
        return True
    if not product_cat:
        return False
    p_norm = normalize_category(product_cat).lower()
    t_norm = normalize_category(target_cat).lower()
    if p_norm == t_norm:
        return True
    p_raw = product_cat.lower().strip()
    t_raw = target_cat.lower().strip()
    return p_raw == t_raw or t_raw in p_raw or p_raw in t_raw


def clear_product_cache(product_id: Optional[int] = None) -> None:
    """Clear in-memory product cache and invalidate Redis catalog cache."""
    _PRODUCT_CACHE.clear()
    try:
        from services.redis_service import RedisService
        RedisService.invalidate_catalog(product_id)
    except Exception as e:
        logger.debug(f"Redis catalog invalidation skipped: {e}")


def get_all_products(category: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieve all products, optionally filtered by category, with tiered L1 (memory) and L2 (Redis) caching."""
    now = time.time()

    # 1. Local in-memory cache (L1: instant < 0.01ms)
    if '__ALL__' in _PRODUCT_CACHE:
        cached_time, all_products = _PRODUCT_CACHE['__ALL__']
        if now - cached_time < _CACHE_TTL_SECONDS:
            if category:
                return [p for p in all_products if is_matching_category(p.get('category', ''), category)]
            return all_products

    # 2. Distributed Read-Through Redis Cache (L2: distributed shared cache)
    try:
        from services.redis_service import RedisService
        cached_catalog = RedisService.get_json('catalog:all_products')
        if cached_catalog and isinstance(cached_catalog, list):
            for p in cached_catalog:
                if p.get('price') is not None:
                    try:
                        p['price'] = float(p['price'])
                    except (ValueError, TypeError):
                        pass
            # Hydrate local L1 cache
            _PRODUCT_CACHE['__ALL__'] = (now, cached_catalog)
            if category:
                return [p for p in cached_catalog if is_matching_category(p.get('category', ''), category)]
            return cached_catalog
    except Exception as re:
        logger.debug(f"Redis get_all_products miss/error: {re}")

    # 3. Relational PostgreSQL Database query
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute('SELECT * FROM products ORDER BY name')
                raw_products = [dict(row) for row in cursor.fetchall()]
                all_products = []
                for item in raw_products:
                    # Provide frontend alias keys
                    item['id'] = item.get('product_id')
                    item['title'] = item.get('name')
                    item['image'] = item.get('image_path')
                    if item.get('price') is not None:
                        try:
                            item['price'] = float(item['price'])
                        except (ValueError, TypeError):
                            pass
                    all_products.append(item)

                # Hydrate in-memory cache
                _PRODUCT_CACHE['__ALL__'] = (now, all_products)

                # Hydrate Redis distributed catalog cache (TTL: 10 minutes)
                try:
                    from services.redis_service import RedisService
                    RedisService.set_json('catalog:all_products', all_products)
                except Exception:
                    pass

                if category:
                    return [p for p in all_products if is_matching_category(p.get('category', ''), category)]
                return all_products
    except Exception as e:
        logger.error(f"Error retrieving products: {e}")
        if '__ALL__' in _PRODUCT_CACHE:
            all_products = _PRODUCT_CACHE['__ALL__'][1]
            if category:
                return [p for p in all_products if is_matching_category(p.get('category', ''), category)]
            return all_products
        raise DatabaseError(f"Failed to retrieve products: {e}") from e


def get_product_by_id(product_id: int) -> Optional[Dict[str, Any]]:
    """Retrieve a product by ID, checking local memory first, then Redis, and finally DB."""
    # 1. Local memory cache (L1: instant < 0.01ms)
    for _, (_, products) in _PRODUCT_CACHE.items():
        for p in products:
            if p.get('product_id') == product_id or p.get('id') == product_id:
                return p

    # 2. Distributed Redis Cache (L2)
    try:
        from services.redis_service import RedisService
        cached_p = RedisService.get_json(f"catalog:product:{product_id}")
        if cached_p and isinstance(cached_p, dict):
            return cached_p
    except Exception:
        pass

    # 3. Database query
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute('SELECT * FROM products WHERE product_id = %s', (product_id,))
                result = cursor.fetchone()
                if result:
                    item = dict(result)
                    item['id'] = item.get('product_id')
                    item['title'] = item.get('name')
                    item['image'] = item.get('image_path')
                    if item.get('price') is not None:
                        try:
                            item['price'] = float(item['price'])
                        except (ValueError, TypeError):
                            pass
                    try:
                        from services.redis_service import RedisService
                        RedisService.set_json(f"catalog:product:{product_id}", item, ttl=600)
                    except Exception:
                        pass
                    return item
                return None
    except Exception as e:
        logger.error(f"Error retrieving product: {e}")
        raise DatabaseError(f"Failed to retrieve product: {e}") from e


def get_product_by_name(name: str) -> Optional[Dict[str, Any]]:
    """Retrieve a product by name (exact or case-insensitive) from database."""
    if not name or not isinstance(name, str):
        return None
    cleaned = name.strip()
    if not cleaned:
        return None

    # Check local memory cache
    for _, (_, products) in _PRODUCT_CACHE.items():
        for p in products:
            if p.get('name', '').lower() == cleaned.lower():
                return p

    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute('SELECT * FROM products WHERE LOWER(name) = LOWER(%s) LIMIT 1', (cleaned,))
                result = cursor.fetchone()
                if not result:
                    # Also try partial matching if name contains packaging specs
                    cursor.execute(
                        'SELECT * FROM products WHERE name ILIKE %s ORDER BY LENGTH(name) ASC LIMIT 1',
                        (f"%{cleaned}%",)
                    )
                    result = cursor.fetchone()
                if result:
                    item = dict(result)
                    item['id'] = item.get('product_id')
                    item['title'] = item.get('name')
                    item['image'] = item.get('image_path')
                    if item.get('price') is not None:
                        try:
                            item['price'] = float(item['price'])
                        except (ValueError, TypeError):
                            pass
                    return item
                return None
    except Exception as e:
        logger.error(f"Error retrieving product by name '{name}': {e}")
        return None


def update_product_price(product_id: int, price: float) -> bool:
    """Update a product's price."""
    updated = False
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute('UPDATE products SET price = %s WHERE product_id = %s', (price, product_id))
                updated = cursor.rowcount > 0

        if updated:
            clear_product_cache(product_id)
        return updated
    except Exception as e:
        logger.error(f"Error updating product price: {e}")
        raise DatabaseError(f"Failed to update product price: {e}") from e


def update_product_stock(product_id: int, stock: int) -> bool:
    """Update a product's stock quantity."""
    updated = False
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute('UPDATE products SET stock = %s WHERE product_id = %s', (stock, product_id))
                updated = cursor.rowcount > 0

        if updated:
            clear_product_cache(product_id)
            try:
                from services.redis_service import RedisService
                RedisService.set_stock(product_id, stock)
            except Exception:
                pass
        return updated
    except Exception as e:
        logger.error(f"Error updating product stock: {e}")
        raise DatabaseError(f"Failed to update product stock: {e}") from e


def update_product(product_id: int, name: Optional[str] = None, price: Optional[float] = None,
                   category: Optional[str] = None, subcategory: Optional[str] = None,
                   image_path: Optional[str] = None, description: Optional[str] = None,
                   stock: Optional[int] = None) -> bool:
    """Update all or selected fields of an existing product in the catalog."""
    updates = []
    params = []
    if name is not None and name.strip():
        updates.append("name = %s")
        params.append(name.strip())
    if price is not None:
        updates.append("price = %s")
        params.append(float(price))
    if category is not None and category.strip():
        updates.append("category = %s")
        params.append(normalize_category(category))
    if subcategory is not None:
        updates.append("subcategory = %s")
        params.append(subcategory.strip())
    if image_path is not None and image_path.strip():
        updates.append("image_path = %s")
        params.append(image_path.strip())
    if description is not None:
        updates.append("description = %s")
        params.append(description.strip())
    if stock is not None:
        updates.append("stock = %s")
        params.append(int(stock))

    if not updates:
        return True

    params.append(product_id)
    query = f"UPDATE products SET {', '.join(updates)} WHERE product_id = %s"
    updated = False
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, tuple(params))
                updated = cursor.rowcount > 0

        if updated:
            clear_product_cache(product_id)
            if stock is not None:
                try:
                    from services.redis_service import RedisService
                    RedisService.set_stock(product_id, int(stock))
                except Exception:
                    pass
        return updated
    except Exception as e:
        logger.error(f"Error updating product #{product_id}: {e}")
        raise DatabaseError(f"Failed to update product: {e}") from e


def add_product(name: str, price: float, category: str, subcategory: str = '',
                image_path: str = '/static/product-placeholder.svg', description: str = '', stock: int = 50) -> Optional[int]:
    """Add a new product to the database catalog."""
    category = normalize_category(category)
    pid = None
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute('''
                    INSERT INTO products (name, price, category, subcategory, image_path, description, stock)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING product_id
                ''', (name, price, category, subcategory, image_path, description, stock))
                row = cursor.fetchone()
                if row:
                    pid = row['product_id']

        if pid:
            clear_product_cache(pid)
            try:
                from services.redis_service import RedisService
                RedisService.set_stock(pid, stock)
            except Exception:
                pass
            return pid
        return None
    except Exception as e:
        logger.error(f"Error adding new product: {e}")
        raise DatabaseError(f"Failed to add product: {e}") from e


def delete_product(product_id: int) -> bool:
    """Delete a product by ID."""
    deleted = False
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute('DELETE FROM products WHERE product_id = %s', (product_id,))
                deleted = cursor.rowcount > 0

        if deleted:
            clear_product_cache(product_id)
            try:
                from services.redis_service import RedisService
                RedisService.delete(RedisService.stock_key(product_id))
            except Exception:
                pass
        return deleted
    except Exception as e:
        logger.error(f"Error deleting product: {e}")
        raise DatabaseError(f"Failed to delete product: {e}") from e


def get_products_paginated(
    page: int = 1,
    per_page: int = 12,
    category: Optional[str] = None,
    search: Optional[str] = None
) -> Dict[str, Any]:
    """
    Retrieve products with pagination, optional category filtering, and keyword search.

    Returns:
        Dict with keys: success, products, total, page, per_page, pages
    """
    import math
    page = max(1, int(page))
    per_page = max(1, min(100, int(per_page)))

    all_products = get_all_products(category=category)
    if search:
        s = search.lower().strip()
        all_products = [
            p for p in all_products
            if s in (p.get('name') or p.get('title') or '').lower()
            or s in (p.get('description') or '').lower()
            or s in (p.get('subcategory') or '').lower()
            or s in (p.get('category') or '').lower()
        ]

    total = len(all_products)
    pages = math.ceil(total / per_page) if total > 0 else 1
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    products = all_products[start_idx:end_idx]

    return {
        'success': True,
        'products': products,
        'total': total,
        'page': page,
        'per_page': per_page,
        'pages': pages
    }


def get_low_stock_products(threshold: int = 10) -> List[Dict[str, Any]]:
    """Retrieve products where stock is equal to or below the given threshold using in-memory catalog."""
    try:
        all_products = get_all_products()
        return [p for p in all_products if (p.get('stock') or 50) <= threshold]
    except Exception as e:
        logger.error(f"Error retrieving low stock products: {e}")
        return []

