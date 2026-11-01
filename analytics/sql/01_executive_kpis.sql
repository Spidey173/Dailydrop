-- =============================================================================
-- DailyDrop SQL Analytics Suite: 01. Executive KPIs & Revenue Growth
-- Computes Monthly GMV, Active Customers, AOV, MoM Growth Rate, and Running Totals.
-- Compatible with PostgreSQL, SQLite, BigQuery, and DuckDB.
-- =============================================================================

WITH monthly_sales AS (
    SELECT 
        SUBSTR(order_date, 1, 7) AS sales_month,
        COUNT(DISTINCT order_id) AS total_orders,
        COUNT(DISTINCT customer_id) AS active_customers,
        SUM(total_amount) AS monthly_gmv,
        SUM(gross_profit) AS monthly_gross_profit,
        ROUND(AVG(total_amount), 2) AS average_order_value
    FROM orders
    WHERE status = 'Delivered'
    GROUP BY SUBSTR(order_date, 1, 7)
),
mom_growth AS (
    SELECT 
        sales_month,
        total_orders,
        active_customers,
        monthly_gmv,
        monthly_gross_profit,
        average_order_value,
        LAG(monthly_gmv, 1) OVER (ORDER BY sales_month) AS prev_month_gmv,
        SUM(monthly_gmv) OVER (ORDER BY sales_month ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS cumulative_gmv
    FROM monthly_sales
)
SELECT 
    sales_month,
    total_orders,
    active_customers,
    monthly_gmv,
    monthly_gross_profit,
    average_order_value,
    COALESCE(
        ROUND(((monthly_gmv - prev_month_gmv) / prev_month_gmv) * 100.0, 2), 
        0.0
    ) AS mom_growth_pct,
    cumulative_gmv
FROM mom_growth
ORDER BY sales_month ASC;
