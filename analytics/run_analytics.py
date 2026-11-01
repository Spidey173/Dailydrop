"""
DailyDrop SQL Analytics Runner & Report Generator
Executes the full suite of analytical SQL queries against the local dataset
and outputs structured executive summaries and markdown tables.
"""

import os
import sqlite3
import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
SQL_DIR = os.path.join(BASE_DIR, 'sql')

def run_suite():
    print("=" * 80)
    print("🚀 Running DailyDrop SQL Analytics Suite")
    print("=" * 80)

    # 1. Verify datasets exist
    orders_csv = os.path.join(DATA_DIR, 'orders.csv')
    order_items_csv = os.path.join(DATA_DIR, 'order_items.csv')
    products_csv = os.path.join(DATA_DIR, 'products.csv')
    customers_csv = os.path.join(DATA_DIR, 'customers.csv')

    for p in [orders_csv, order_items_csv, products_csv, customers_csv]:
        if not os.path.exists(p):
            print(f"Dataset missing: {p}. Running data generator first...")
            from analytics.generate_analytics_data import run as gen_data
            gen_data()
            break

    # 2. Ingest CSVs into in-memory SQLite
    print("📥 Loading datasets into high-performance in-memory analytics engine...")
    conn = sqlite3.connect(':memory:')
    
    df_orders = pd.read_csv(orders_csv)
    df_items = pd.read_csv(order_items_csv)
    df_products = pd.read_csv(products_csv)
    df_customers = pd.read_csv(customers_csv)

    df_orders.to_sql('orders', conn, index=False)
    df_items.to_sql('order_items', conn, index=False)
    df_products.to_sql('products', conn, index=False)
    df_customers.to_sql('customers', conn, index=False)

    print(f"   • Loaded {len(df_orders):,} orders")
    print(f"   • Loaded {len(df_items):,} order items")
    print(f"   • Loaded {len(df_products):,} products")
    print(f"   • Loaded {len(df_customers):,} customers")
    print("-" * 80)

    # 3. Execute SQL queries and display findings
    sql_files = [
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

        # Clean SQL queries: remove comment lines
        cleaned_query = "\n".join(line for line in query.splitlines() if not line.strip().startswith('--'))
        sub_queries = [q.strip() for q in cleaned_query.split(';') if q.strip()]
        
        for idx, sq in enumerate(sub_queries):
            try:
                res_df = pd.read_sql_query(sq, conn)
                print(res_df.head(10).to_string(index=False))
                if len(res_df) > 10:
                    print(f"... [{len(res_df) - 10} additional rows computed]")

                # Convert to clean markdown table without tabulate
                headers = list(res_df.columns)
                col_widths = {h: max(len(str(h)), *(len(str(v)) for v in res_df[h].head(15))) for h in headers}
                header_row = "| " + " | ".join(str(h).ljust(col_widths[h]) for h in headers) + " |"
                separator_row = "| " + " | ".join("-" * col_widths[h] for h in headers) + " |"
                data_rows = []
                for _, r in res_df.head(15).iterrows():
                    data_rows.append("| " + " | ".join(str(r[h]).ljust(col_widths[h]) for h in headers) + " |")
                md_table = "\n".join([header_row, separator_row] + data_rows)

                report_sections.append(f"### {title}\n\n```sql\n{sq}\n```\n\n{md_table}\n\n")
            except Exception as e:
                print(f"Error executing sub-query {idx+1}: {e}")

    # Write Markdown summary report
    report_path = os.path.join(BASE_DIR, 'ANALYSIS_RESULTS.md')
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("# 🛒 DailyDrop E-Commerce & Quick-Commerce Data Analytics Report\n\n")
        f.write(f"Generated automatically on {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')} using SQLite in-memory engine.\n\n")
        f.write("".join(report_sections))

    print("\n" + "=" * 80)
    print(f"✅ Full analytics suite completed! Detailed results saved to: {report_path}")
    print("=" * 80)

if __name__ == '__main__':
    run_suite()
