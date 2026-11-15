"""
Catalog validation service.
Validates cart items against database catalog and computes authoritative totals
using exact Decimal arithmetic.
"""
import logging
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Tuple
from services.currency_service import CurrencyService

logger = logging.getLogger(__name__)

DELIVERY_THRESHOLD = Decimal('500.00')
DELIVERY_FEE = Decimal('30.00')
FREE_FEE = Decimal('0.00')


class ValidationResult(tuple):
    """
    Tuple-compatible result preserving 5-element unpacking:
        (valid, error_message, resolved_items, item_quantities, authoritative_total)
    while carrying pre-fetched item_stocks and item_names to avoid N+1 queries.
    """
    def __new__(cls, valid, err, resolved_items, item_quantities, authoritative_total, item_stocks=None, item_names=None):
        inst = super().__new__(cls, (valid, err, resolved_items, item_quantities, authoritative_total))
        inst.item_stocks = item_stocks or {}
        inst.item_names = item_names or {}
        return inst


class CatalogValidationService:
    """Handles catalog resolution, item validation, and authoritative price calculation."""

    @classmethod
    def validate_and_resolve_cart(
        cls,
        cursor: Any,
        items_list: List[Dict[str, Any]]
    ) -> Tuple[bool, Optional[str], List[Dict[str, Any]], Dict[int, int], float]:
        """
        Inspect cart items and strictly resolve against real catalog products using Decimal calculations.
        Batches product ID lookups using product_id = ANY(%s) to eliminate N+1 queries.
        Returns:
            ValidationResult compatible with (success, error_message, resolved_items, item_quantities, authoritative_total)
        """
        resolved_items = []
        item_quantities = defaultdict(int)
        item_stocks = {}
        item_names = {}

        # 1. Collect all numeric product IDs for batch lookup
        numeric_pids = []
        for item in items_list:
            if not isinstance(item, dict):
                return ValidationResult(False, 'Invalid cart item structure', [], {}, 0.0)
            pid = item.get('product_id') or item.get('id')
            if pid is not None:
                try:
                    numeric_pids.append(int(pid))
                except (ValueError, TypeError):
                    pass

        # 2. Batch query products by ID using product_id = ANY(%s) to eliminate N+1 roundtrips
        products_by_id = {}
        if numeric_pids:
            try:
                unique_pids = list(set(numeric_pids))
                cursor.execute(
                    "SELECT product_id, name, stock, price, image_path FROM products WHERE product_id = ANY(%s)",
                    (unique_pids,)
                )
                for r in cursor.fetchall():
                    pid_val = r['product_id'] if isinstance(r, dict) else r[0]
                    products_by_id[pid_val] = r
            except Exception as db_err:
                logger.error(f"Database error during batch product lookup: {db_err}")
                return ValidationResult(False, 'Database error during catalog lookup', [], {}, 0.0)

        for item in items_list:
            qty = int(item.get('quantity', 1))
            if qty <= 0:
                return ValidationResult(False, 'Product quantity must be at least 1', [], {}, 0.0)

            name = item.get('name', '')
            img = item.get('image') or item.get('image_path') or '/static/logo1.webp'
            pid = item.get('product_id') or item.get('id')

            prod_row = None
            if pid is not None:
                try:
                    prod_row = products_by_id.get(int(pid))
                except (ValueError, TypeError):
                    prod_row = None

            if not prod_row and name:
                try:
                    cursor.execute("SELECT product_id, name, stock, price, image_path FROM products WHERE LOWER(name) = LOWER(%s)", (name.strip(),))
                    prod_row = cursor.fetchone()
                except Exception as db_err:
                    logger.error(f"Database error during product name lookup '{name}': {db_err}")
                    return ValidationResult(False, 'Database error during catalog lookup', [], {}, 0.0)

            if not prod_row and name:
                try:
                    cursor.execute("SELECT product_id, name, stock, price, image_path FROM products WHERE name ILIKE %s ORDER BY LENGTH(name) ASC LIMIT 1", (f"%{name.strip()}%",))
                    prod_row = cursor.fetchone()
                except Exception as db_err:
                    logger.error(f"Database error during product pattern lookup '{name}': {db_err}")
                    return ValidationResult(False, 'Database error during catalog lookup', [], {}, 0.0)

            if not prod_row:
                identifier = name or (f"ID #{pid}" if pid else "item")
                logger.warning(f"Rejected checkout: Product '{identifier}' not found in catalog database.")
                return ValidationResult(False, f"Product '{identifier}' not found in catalog", [], {}, 0.0)

            r_pid = prod_row['product_id'] if isinstance(prod_row, dict) else prod_row[0]
            r_name = prod_row['name'] if isinstance(prod_row, dict) else prod_row[1]
            raw_stock = prod_row.get('stock') if isinstance(prod_row, dict) else prod_row[2]
            raw_price = prod_row.get('price') if isinstance(prod_row, dict) else prod_row[3]

            item_stocks[r_pid] = raw_stock
            item_names[r_pid] = r_name

            try:
                dec_price = CurrencyService.to_decimal(raw_price)
                if dec_price <= Decimal('0.00'):
                    logger.error(f"Non-positive authoritative price in catalog item #{r_pid} ('{r_name}')")
                    return ValidationResult(False, f"Pricing error for product '{r_name}'. Order cannot proceed.", [], {}, 0.0)
            except (ValueError, InvalidOperation):
                logger.error(f"Missing or invalid authoritative price for catalog item #{r_pid} ('{r_name}')")
                return ValidationResult(False, f"Pricing error for product '{r_name}'. Order cannot proceed.", [], {}, 0.0)

            r_price = float(dec_price)
            r_img = (prod_row['image_path'] if isinstance(prod_row, dict) else prod_row[4]) or img

            dec_qty = Decimal(qty)
            subtotal_dec = CurrencyService.round_money(dec_price * dec_qty)
            subtotal = float(subtotal_dec)

            item_quantities[r_pid] += qty
            resolved_items.append({
                'product_id': r_pid,
                'name': r_name,
                'price': r_price,
                'quantity': qty,
                'image': r_img,
                'subtotal': subtotal,
                '_subtotal_dec': subtotal_dec
            })

        computed_subtotal_dec = sum((i['_subtotal_dec'] for i in resolved_items), Decimal('0.00'))
        computed_fee_dec = FREE_FEE if computed_subtotal_dec >= DELIVERY_THRESHOLD else DELIVERY_FEE
        authoritative_total_dec = CurrencyService.round_money(computed_subtotal_dec + computed_fee_dec)

        # Remove internal decimal calculation helper before serialization
        for i in resolved_items:
            i.pop('_subtotal_dec', None)

        authoritative_total = float(authoritative_total_dec)
        return ValidationResult(
            True, None, resolved_items, item_quantities, authoritative_total,
            item_stocks=item_stocks, item_names=item_names
        )
