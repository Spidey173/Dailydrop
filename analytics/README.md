# 📊 DailyDrop Quick-Commerce Data Analytics & BI Suite

Welcome to the **DailyDrop Data Analytics Suite** — an end-to-end, enterprise-grade e-commerce analytics ecosystem demonstrating advanced SQL, cloud OLAP data processing on Neon PostgreSQL, customer segmentation (RFM), cohort retention, logistics SLA optimization, and inventory Pareto stratification.

---

## 🚀 Quick Start (Zero Setup Required)

Everything is powered directly by your **Neon PostgreSQL** production database and standard data science tools:

### 1. Run the Full Analytics Engine & Generate Reports
```bash
python3 analytics/run_analytics.py
```
*This executes all 6 advanced SQL modules directly against your live **Neon PostgreSQL** database, prints formatted ASCII tables to the terminal, and exports a comprehensive Markdown report to [`analytics/ANALYSIS_RESULTS.md`](./ANALYSIS_RESULTS.md).*

### 2. (Optional) Re-generate the 12-Month E-Commerce Dataset
```bash
python3 analytics/generate_analytics_data.py
```
*Generates 3,280+ realistic transactional orders, 11,800+ itemized rows, 250 customer profiles, and pre-calculated RFM metrics across 241 real catalog products.*

### 3. Open the Interactive Portfolio Jupyter Notebook
```bash
jupyter notebook analytics/notebooks/DailyDrop_Analytics_Portfolio.ipynb
# or open directly in VS Code / Cursor / PyCharm
```

---

## 📁 Repository Structure

```
analytics/
├── CASE_STUDY.md                   # 🌟 Executive Case Study, Business Strategy & Interview Defense Guide
├── ANALYSIS_RESULTS.md             # 📈 Generated markdown reports from all 6 analytical SQL queries
├── requirements-analytics.txt      # 📦 Python data science dependencies (pandas, matplotlib, seaborn, etc.)
├── generate_analytics_data.py      # ⚙️ Real-world synthetic transaction generator (12 months, 5 cities)
├── run_analytics.py                # 🚀 Neon PostgreSQL analytics engine & markdown table reporter
├── build_notebook.py               # 🛠️ Programmatic Jupyter Notebook builder
├── data/                           # 📂 Extracted CSV datasets for data warehousing
│   ├── products.csv                # 241 SKUs across 10 categories with cost and margins
│   ├── customers.csv               # 250 customer profiles with acquisition cohorts and personas
│   ├── orders.csv                  # 3,281 orders with timestamps, fees, delivery durations
│   ├── order_items.csv             # 11,851 line items with unit costs and gross margins
│   └── customer_rfm.csv            # Precomputed RFM scores & lifecycle segment tags
├── notebooks/                      # 📓 Visual Storytelling & Exploratory Data Analysis
│   └── DailyDrop_Analytics_Portfolio.ipynb # 16-cell portfolio notebook with charts & insights
└── sql/                            # 🗄️ Advanced SQL Suite (CTEs, Window Functions, Self-Joins)
    ├── 01_executive_kpis.sql       # Monthly GMV, AOV, MoM growth rate with LAG()
    ├── 02_customer_rfm_segmentation.sql # Recency, Frequency, Monetary scoring via NTILE(5)
    ├── 03_monthly_cohort_retention.sql  # Monthly cohort retention percentage matrix
    ├── 04_market_basket_analysis.sql    # Self-joins identifying frequent co-purchases & lift
    ├── 05_dispatch_and_sla_logistics.sql# 10-minute delivery duration & peak-hour SLA adherence
    └── 06_abc_inventory_pareto.sql      # Pareto 80/20 inventory ranking with cumulative revenue %
```

---

## 🎯 Analytical Highlights

| Dimension | Key Finding | Strategic Metric |
| :--- | :--- | :--- |
| **Gross Merchandise Value** | Reached ₹1,648,858 across 3,281 delivered orders | **₹502.55** AOV, 25.2% blended gross margin |
| **10-Minute SLA Compliance** | Fast micro-fulfillment dark store turnaround | **97.9%** delivered under 10 min (7.24 min avg) |
| **Customer Concentration** | Champions & Loyal regular customers drive majority value | **Top 20% users drive 52.4%** of GMV |
| **30-Day Cohort Retention** | Significantly outperforms quick-commerce baseline | **58.2%** Month 1 retention; 35% long-term plateau |
| **Inventory Pareto Rule** | Top 20% SKUs generate 80% of revenue | **Class A (20% SKUs) = 80% GMV** |

---

## 📖 In-Depth Documentation

For the full analytical narrative, business recommendations, and data analyst interview answers, see [**CASE_STUDY.md**](./CASE_STUDY.md).

