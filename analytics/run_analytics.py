"""
DailyDrop SQL Analytics Runner & Report Generator
Executes the full suite of analytical SQL queries against the live
Neon PostgreSQL production database and outputs executive summaries and markdown reports.
"""

import os
import sys
import pandas as pd
from typing import List, Tuple

# Ensure project root is in sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from config import Config
from database import get_db_connection, RealDictCursor

ANALYTICS_DIR = os.path.dirname(os.path.abspath(__file__))
SQL_DIR = os.path.join(ANALYTICS_DIR, 'sql')


def run_suite():
    print("=" * 80)
    print("🚀 Running DailyDrop SQL Analytics Suite on Neon PostgreSQL")
    print("=" * 80)

    # 1. Verify connection to Neon PostgreSQL
    print("📥 Connecting to Neon PostgreSQL...")
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT 
                    (SELECT COUNT(*) FROM orders) AS total_orders,
                    (SELECT COUNT(*) FROM order_items) AS total_order_items,
                    (SELECT COUNT(*) FROM products) AS total_products,
                    (SELECT COUNT(*) FROM users) AS total_users;
            """)
            counts = cur.fetchone()
            print(f"   • Orders in Neon       : {counts['total_orders']:,}")
            print(f"   • Order Items in Neon  : {counts['total_order_items']:,}")
            print(f"   • Products in Neon     : {counts['total_products']:,}")
            print(f"   • Customers in Neon    : {counts['total_users']:,}")
            print("-" * 80)

            # 2. Execute SQL query suite
            sql_files: List[Tuple[str, str]] = [
                ('01_executive_kpis.sql', '📈 Executive Revenue & Monthly MoM Growth KPIs'),
                ('02_customer_rfm_segmentation.sql', '🎯 Customer RFM Segmentation & Lifecycle Clusters'),
                ('03_monthly_cohort_retention.sql', '🔄 Monthly Cohort Retention Heatmap Analysis'),
                ('04_market_basket_analysis.sql', '🛒 Market Basket Analysis & Product Co-Purchases'),
                ('05_dispatch_and_sla_logistics.sql', '⚡ Quick-Commerce 10-Minute SLA & Hourly Rush Analysis'),
                ('06_abc_inventory_pareto.sql', '📦 ABC Inventory Classification (Pareto 80/20 Rule)')
            ]

            report_sections = []

            for filename, title in sql_files:
                filepath = os.path.join(SQL_DIR, filename)
                if not os.path.exists(filepath):
                    continue

                with open(filepath, 'r', encoding='utf-8') as f:
                    query = f.read()

                print(f"\n{title}")
                print("=" * 80)

                # Clean comments
                cleaned_query = "\n".join(
                    line for line in query.splitlines() if not line.strip().startswith('--')
                )
                sub_queries = [q.strip() for q in cleaned_query.split(';') if q.strip()]

                for idx, sq in enumerate(sub_queries):
                    try:
                        cur.execute(sq)
                        rows = cur.fetchall()
                        if not rows:
                            print("(No rows returned)")
                            continue

                        res_df = pd.DataFrame([dict(r) for r in rows])
                        print(res_df.head(10).to_string(index=False))
                        if len(res_df) > 10:
                            print(f"... [{len(res_df) - 10} additional rows computed]")

                        # Markdown formatting
                        headers = list(res_df.columns)
                        col_widths = {
                            h: max(len(str(h)), *(len(str(v)) for v in res_df[h].head(15)))
                            for h in headers
                        }
                        header_row = "| " + " | ".join(str(h).ljust(col_widths[h]) for h in headers) + " |"
                        separator_row = "| " + " | ".join("-" * col_widths[h] for h in headers) + " |"
                        data_rows = []
                        for _, r in res_df.head(15).iterrows():
                            data_rows.append(
                                "| " + " | ".join(str(r[h]).ljust(col_widths[h]) for h in headers) + " |"
                            )
                        md_table = "\n".join([header_row, separator_row] + data_rows)

                        report_sections.append(f"### {title}\n\n```sql\n{sq}\n```\n\n{md_table}\n\n")
                    except Exception as e:
                        print(f"Error executing sub-query {idx+1}: {e}")

    # Write Markdown summary report
    report_path = os.path.join(ANALYTICS_DIR, 'ANALYSIS_RESULTS.md')
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("# 🛒 DailyDrop E-Commerce & Quick-Commerce Data Analytics Report\n\n")
        f.write(f"Generated on {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')} using **Neon PostgreSQL** cloud engine.\n\n")
        f.write("".join(report_sections))

    print("\n" + "=" * 80)
    print(f"✅ Full analytics suite completed on Neon PostgreSQL! Results saved to: {report_path}")
    print("=" * 80)


if __name__ == '__main__':
    run_suite()
