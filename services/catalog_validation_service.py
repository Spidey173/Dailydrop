"""
Catalog validation service.
Validates cart items against database catalog and computes authoritative totals.
"""
import json
import logging
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class CatalogValidationService:
    """Handles catalog resolution, item validation, and authoritative price calculation."""

    @classmethod
    def validate_and_resolve_cart(
        cls,
        cursor: Any,
        items_list: List[Dict[str, Any]]
    ) -> Tuple[bool, Optional[str], List[Dict[str, Any]], Dict[int, int], float]:
        """
        Inspect cart items and strictly resolve against real catalog products.
        Returns:
            (success, error_message, resolved_items, item_quantities, authoritative_total)
        """
        resolved_items = []
        item_quantities = defaultdict(int)

        for item in items_list:
            if not isinstance(item, dict):
                return False, 'Invalid cart item structure', [], {}, 0.0
            qty = int(item.get('quantity', 1))
            if qty <= 0:
                return False, 'Product quantity must be at least 1', [], {}, 0.0

            name = item.get('name', '')
            img = item.get('image') or item.get('image_path') or '/static/logo1.webp'
            pid = item.get('product_id') or item.get('id')

            prod_row = None
            if pid is not None:
                try:
                    cursor.execute("SELECT product_id, name, stock, price, image_path FROM products WHERE product_id = %s", (int(pid),))
                    prod_row = cursor.fetchone()
                except (ValueError, TypeError):
                    prod_row = None
                except Exception as db_err:
                    logger.error(f"Database error during product lookup #{pid}: {db_err}")
                    return False, 'Database error during catalog lookup', [], {}, 0.0

            if not prod_row and name:
                try:
                    cursor.execute("SELECT product_id, name, stock, price, image_path FROM products WHERE LOWER(name) = LOWER(%s)", (name.strip(),))
                    prod_row = cursor.fetchone()
                except Exception as db_err:
                    logger.error(f"Database error during product name lookup '{name}': {db_err}")
                    return False, 'Database error during catalog lookup', [], {}, 0.0

            if not prod_row and name:
                try:
                    cursor.execute("SELECT product_id, name, stock, price, image_path FROM products WHERE name ILIKE %s ORDER BY LENGTH(name) ASC LIMIT 1", (f"%{name.strip()}%",))
                    prod_row = cursor.fetchone()
                except Exception as db_err:
                    logger.error(f"Database error during product pattern lookup '{name}': {db_err}")
                    return False, 'Database error during catalog lookup', [], {}, 0.0

            if not prod_row:
                identifier = name or (f"ID #{pid}" if pid else "item")
                logger.warning(f"Rejected checkout: Product '{identifier}' not found in catalog database.")
                return False, f"Product '{identifier}' not found in catalog", [], {}, 0.0

            r_pid = prod_row['product_id'] if isinstance(prod_row, dict) else prod_row[0]
            r_name = prod_row['name'] if isinstance(prod_row, dict) else prod_row[1]
            raw_price = prod_row.get('price') if isinstance(prod_row, dict) else prod_row[3]

            if raw_price is None or float(raw_price) <= 0:
                logger.error(f"Missing authoritative price in database for catalog item #{r_pid} ('{r_name}')")
                return False, f"Pricing error for product '{r_name}'. Order cannot proceed.", [], {}, 0.0

            r_price = float(raw_price)
            r_img = (prod_row['image_path'] if isinstance(prod_row, dict) else prod_row[4]) or img

            subtotal = round(r_price * qty, 2)
            item_quantities[r_pid] += qty
            resolved_items.append({
                'product_id': r_pid,
                'name': r_name,
                'price': r_price,
                'quantity': qty,
                'image': r_img,
                'subtotal': subtotal
            })

        computed_subtotal = round(sum(i['subtotal'] for i in resolved_items), 2)
        computed_fee = 0.0 if computed_subtotal >= 500.0 else 30.0
        authoritative_total = round(computed_subtotal + computed_fee, 2)
        return True, None, resolved_items, item_quantities, authoritative_total
