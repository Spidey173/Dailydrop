"""
Versioned Database Migration Runner for Daily Drop.

Tracks and applies incremental SQL migration scripts stored in the migrations/ directory.
Guarantees idempotent, transactional execution and maintains the `schema_migrations` audit table.

Usage:
    python -m migrations.runner
"""

import os
import glob
import logging
from typing import List, Tuple
from database import get_db_connection, DatabaseError

logger = logging.getLogger("dailydrop.migrations")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

MIGRATIONS_DIR = os.path.dirname(os.path.abspath(__file__))


def get_applied_migrations() -> List[str]:
    """Retrieve list of already applied migration file versions."""
    applied = []
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS schema_migrations (
                        version VARCHAR(100) PRIMARY KEY,
                        applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                cursor.execute("SELECT version FROM schema_migrations ORDER BY version ASC")
                rows = cursor.fetchall()
                for r in rows:
                    val = r['version'] if isinstance(r, dict) else r[0]
                    applied.append(val)
    except Exception as e:
        logger.warning(f"Could not query schema_migrations: {e}")
    return applied


def run_migrations() -> Tuple[int, List[str]]:
    """
    Discover, sort, and execute all pending migrations in alphabetical version order.

    Returns:
        Tuple of (applied_count, list_of_applied_versions)
    """
    sql_files = sorted(glob.glob(os.path.join(MIGRATIONS_DIR, "*.sql")))
    if not sql_files:
        logger.info("No migration SQL files found.")
        return 0, []

    applied_set = set(get_applied_migrations())
    applied_this_run = []

    for file_path in sql_files:
        version = os.path.basename(file_path)
        if version in applied_set:
            continue

        logger.info(f"Applying database migration: {version}...")
        with open(file_path, "r", encoding="utf-8") as f:
            sql_content = f.read()

        try:
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    # Execute migration script
                    cursor.execute(sql_content)
                    # Record migration in schema_migrations audit log
                    cursor.execute(
                        "INSERT INTO schema_migrations (version) VALUES (%s)",
                        (version,)
                    )
            logger.info(f"✓ Migration {version} applied successfully.")
            applied_this_run.append(version)
        except Exception as e:
            logger.error(f"✗ Failed to apply migration {version}: {e}")
            raise DatabaseError(f"Migration {version} failed: {e}") from e

    if not applied_this_run:
        logger.info("Database schema is fully up-to-date. Zero pending migrations.")
    else:
        logger.info(f"Successfully applied {len(applied_this_run)} migration(s).")

    return len(applied_this_run), applied_this_run


if __name__ == "__main__":
    count, versions = run_migrations()
    print(f"Migration run complete: {count} applied ({versions})")
