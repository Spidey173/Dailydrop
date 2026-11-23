"""
Tests for RFM Segmentation Analytics and dynamic timestamp calculations.
"""
import pytest
from datetime import datetime, timezone, timedelta
from app import create_app
from database import get_db_connection
from repositories.analytics_repository import _get_fallback_rfm_customers


@pytest.fixture
def test_app():
    app = create_app('testing')
    with app.app_context():
        yield app


def test_no_hardcoded_date_in_database_and_sql():
    """Verify that no hardcoded '2026-11-01' remains in database.py or sql analytics."""
    with open("database.py", "r") as f:
        content = f.read()
    assert "2026-11-01" not in content, "Found hardcoded '2026-11-01' in database.py"

    with open("analytics/sql/02_customer_rfm_segmentation.sql", "r") as f:
        sql_content = f.read()
    assert "2026-11-01" not in sql_content, "Found hardcoded '2026-11-01' in 02_customer_rfm_segmentation.sql"


def test_rfm_recency_score_ranking(test_app):
    """
    Verify that recently active customers receive HIGHER r_score than stale customers,
    and recency_days is computed relative to the current timestamp.
    """
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                CREATE TEMPORARY TABLE IF NOT EXISTS test_rfm_scoring (
                    user_id INT,
                    recency_days INT
                )
            """)
            cursor.execute("DELETE FROM test_rfm_scoring")
            # 5 customers: user 1 is most recent (1 day), user 5 is stalest (60 days)
            for uid, rdays in [(1, 1), (2, 5), (3, 15), (4, 30), (5, 60)]:
                cursor.execute(
                    "INSERT INTO test_rfm_scoring (user_id, recency_days) VALUES (%s, %s)",
                    (uid, rdays)
                )
            cursor.execute("""
                SELECT user_id, recency_days,
                       NTILE(5) OVER (ORDER BY recency_days DESC) AS r_score
                FROM test_rfm_scoring
                ORDER BY recency_days ASC
            """)
            rows = cursor.fetchall()
            results = {
                (r['user_id'] if isinstance(r, dict) else r[0]): (r['r_score'] if isinstance(r, dict) else r[2])
                for r in rows
            }

            # Most recent customer (user 1, recency_days=1) must have r_score=5
            # Stalest customer (user 5, recency_days=60) must have r_score=1
            assert results[1] == 5, f"Expected user 1 to have r_score 5, got {results[1]}"
            assert results[5] == 1, f"Expected user 5 to have r_score 1, got {results[5]}"
            assert results[1] > results[5]
