"""
Seed script for Daily Drop database.
Populates initial administrative accounts, demo customer accounts, and catalog products.

Usage:
    DATABASE_URL=<neon-direct-url> python seed.py
    python seed.py
    python -m seed
"""
import os
import sys
import json
import logging
from typing import Optional
from werkzeug.security import generate_password_hash
from core.database import get_db_connection, DatabaseError

logger = logging.getLogger("dailydrop.seed")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def seed_users() -> None:
    """Seed initial administrator and demo customer accounts idempotently."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                # 1. Admin account
                admin_hashed_password = generate_password_hash('Dailydrop@173')
                cursor.execute(
                    "SELECT id FROM users WHERE role = 'admin' OR email = %s OR email = %s",
                    ('admin_dailydrop@gmail.com', 'admin@dailydrop.com')
                )
                admin_user = cursor.fetchone()
                if not admin_user:
                    cursor.execute(
                        """
                        INSERT INTO users (name, email, password, role)
                        VALUES ('Admin User', 'admin_dailydrop@gmail.com', %s, 'admin')
                        """,
                        (admin_hashed_password,)
                    )
                    logger.info("✓ Admin account created successfully.")
                else:
                    logger.info("Admin account already exists.")

                # 2. Demo customer account
                demo_hashed_password = generate_password_hash('Demouser@123')
                cursor.execute("SELECT id FROM users WHERE email = %s", ('demo_dailydrop@gmail.com',))
                demo_user = cursor.fetchone()
                if not demo_user:
                    cursor.execute(
                        """
                        INSERT INTO users (name, email, password, role)
                        VALUES ('Demo Customer', 'demo_dailydrop@gmail.com', %s, 'customer')
                        """,
                        (demo_hashed_password,)
                    )
                    logger.info("✓ Demo customer account created successfully.")
                else:
                    logger.info("Demo customer account already exists.")
    except Exception as e:
        logger.error(f"Error seeding users: {e}")
        raise DatabaseError(f"Failed to seed users: {e}") from e


def seed_products(seed_file_path: Optional[str] = None) -> int:
    """Seed catalog products from seeds/products.json if products table is empty."""
    if seed_file_path is None:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        json_path = os.path.join(base_dir, 'seeds', 'products.json')
        js_path = os.path.join(base_dir, 'static', 'js', 'products.js')
        seed_file_path = json_path if os.path.exists(json_path) else js_path

    if not os.path.exists(seed_file_path):
        logger.warning(f"Products seed file not found at: {seed_file_path}")
        return 0

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) as count FROM products")
                row = cursor.fetchone()
                product_count = row['count'] if isinstance(row, dict) else row[0]
                if product_count > 0:
                    logger.info(f"Products catalog already contains {product_count} items. Skipping product seed.")
                    return product_count

                with open(seed_file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                if seed_file_path.endswith('.json'):
                    raw_products = json.loads(content)
                else:
                    start = content.find('[')
                    end = content.rfind(']') + 1
                    if start == -1 or end == 0:
                        logger.warning("No JSON array found in seed file")
                        return 0
                    raw_products = json.loads(content[start:end])

                for pid, p in enumerate(raw_products, start=1):
                    unique_stock = 30 + ((pid * 7) % 65)
                    cursor.execute(
                        """
                        INSERT INTO products (product_id, name, price, category, subcategory, image_path, description, stock)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (product_id) DO NOTHING
                        """,
                        (
                            pid,
                            p.get('title', 'Product'),
                            float(p.get('price', 0)),
                            p.get('category', 'Grocery'),
                            p.get('subcategory', ''),
                            p.get('image', '/static/product-placeholder.svg'),
                            p.get('description', ''),
                            unique_stock
                        )
                    )

                try:
                    cursor.execute(
                        "SELECT setval(pg_get_serial_sequence('products', 'product_id'), COALESCE(MAX(product_id), 1)) FROM products;"
                    )
                except Exception:
                    pass

                logger.info(f"✓ Seeded {len(raw_products)} products into catalog.")
                return len(raw_products)
    except Exception as e:
        logger.error(f"Error seeding products: {e}")
        raise DatabaseError(f"Failed to seed products: {e}") from e


def seed_database() -> None:
    """Run all database seeders idempotently."""
    logger.info("Starting database seeding...")
    seed_users()
    seed_products()
    logger.info("✓ Database seeding complete.")


if __name__ == "__main__":
    try:
        seed_database()
        sys.exit(0)
    except Exception as exc:
        logger.error(f"Seeding failed: {exc}")
        sys.exit(1)

