"""
Product service managing catalog retrieval, inventory updates, and product administration.
"""
from typing import Optional, List, Dict, Any, Tuple
import logging
from database import (
    get_all_products, get_product_by_id, update_product_price,
    update_product_stock, add_product, delete_product, get_low_stock_products,
    DatabaseError
)

logger = logging.getLogger(__name__)


class ProductService:
    """Service providing catalog queries and product inventory management."""

    @staticmethod
    def get_products_by_category(category: Optional[str] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Retrieve products filtered by category with optional limit."""
        try:
            products = get_all_products(category)
            if limit and limit > 0:
                return products[:limit]
            return products
        except DatabaseError as e:
            logger.error(f"Error fetching products for category '{category}': {e}")
            return []

    @staticmethod
    def get_product(product_id: int) -> Optional[Dict[str, Any]]:
        """Retrieve product by ID."""
        try:
            return get_product_by_id(product_id)
        except DatabaseError as e:
            logger.error(f"Error fetching product ID {product_id}: {e}")
            return None

    @staticmethod
    def update_price(product_id: int, price: float) -> Tuple[bool, str]:
        """Update product price."""
        if price <= 0:
            return False, 'Price must be greater than zero'
        try:
            success = update_product_price(product_id, price)
            if success:
                return True, 'Price updated successfully'
            return False, 'Product not found'
        except DatabaseError as e:
            logger.error(f"Error updating price for product {product_id}: {e}")
            return False, 'Failed to update price'

    @staticmethod
    def update_stock(product_id: int, stock: int) -> Tuple[bool, str]:
        """Update product stock."""
        if stock < 0:
            return False, 'Stock quantity cannot be negative'
        try:
            success = update_product_stock(product_id, stock)
            if success:
                return True, 'Stock updated successfully'
            return False, 'Product not found'
        except DatabaseError as e:
            logger.error(f"Error updating stock for product {product_id}: {e}")
            return False, 'Failed to update stock'

    @staticmethod
    def create_product(name: str, price: float, category: str, subcategory: str = '',
                       image_path: str = '/static/logo.webp', description: str = '',
                       stock: int = 50) -> Tuple[bool, str, Optional[int]]:
        """Add a new product to catalog."""
        if not name or price <= 0 or not category:
            return False, 'Invalid product parameters', None
        try:
            pid = add_product(name, price, category, subcategory, image_path, description, stock)
            if pid:
                return True, 'Product added successfully', pid
            return False, 'Failed to insert product', None
        except DatabaseError as e:
            logger.error(f"Error creating product '{name}': {e}")
            return False, 'Failed to create product', None

    @staticmethod
    def remove_product(product_id: int) -> Tuple[bool, str]:
        """Delete a product by ID."""
        try:
            success = delete_product(product_id)
            if success:
                return True, 'Product deleted successfully'
            return False, 'Product not found'
        except DatabaseError as e:
            logger.error(f"Error deleting product {product_id}: {e}")
            return False, 'Failed to delete product'

    @staticmethod
    def get_low_stock(threshold: int = 10) -> List[Dict[str, Any]]:
        """Retrieve low stock products."""
        try:
            return get_low_stock_products(threshold)
        except DatabaseError as e:
            logger.error(f"Error retrieving low stock products: {e}")
            return []

    @staticmethod
    def search_products(query: str, limit: int = 8) -> List[Dict[str, Any]]:
        """Search products by name, category, and subcategory for live autocomplete."""
        query = (query or '').strip()
        if not query:
            return []
        try:
            from database import get_db_connection
            from psycopg2.extras import RealDictCursor
            with get_db_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    search_pattern = f"%{query}%"
                    cursor.execute('''
                        SELECT product_id, name, price, category, subcategory, image_path, description, stock
                        FROM products
                        WHERE name ILIKE %s OR category ILIKE %s OR subcategory ILIKE %s OR description ILIKE %s
                        ORDER BY 
                            CASE 
                                WHEN name ILIKE %s THEN 1
                                WHEN name ILIKE %s THEN 2
                                ELSE 3
                            END,
                            name ASC
                        LIMIT %s
                    ''', (
                        search_pattern, search_pattern, search_pattern, search_pattern,
                        f"{query}%", search_pattern, limit
                    ))
                    rows = cursor.fetchall()
                    results = []
                    for r in rows:
                        item = dict(r)
                        item['price'] = float(item['price']) if item.get('price') is not None else 0.0
                        results.append(item)
                    return results
        except DatabaseError as e:
            logger.error(f"Error searching products for '{query}': {e}")
            return []

