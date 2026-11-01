-- =============================================================================
-- DailyDrop SQL Analytics Suite: 03. Customer Cohort Retention Analysis
-- Tracks repeat purchasing behavior by acquisition cohort month across time.
-- Target Engine: Neon PostgreSQL
-- =============================================================================

WITH customer_first_purchase AS (
    SELECT 
        user_id,
        MIN(TO_CHAR(order_date, 'YYYY-MM')) AS cohort_month
    FROM orders
    WHERE status = 'Delivered'
    GROUP BY user_id
),
cohort_size AS (
    SELECT 
        cohort_month,
        COUNT(DISTINCT user_id) AS cohort_customer_count
    FROM customer_first_purchase
    GROUP BY cohort_month
),
customer_orders_by_month AS (
    SELECT DISTINCT
        o.user_id,
        fp.cohort_month,
        TO_CHAR(o.order_date, 'YYYY-MM') AS order_month
    FROM orders o
    JOIN customer_first_purchase fp ON o.user_id = fp.user_id
    WHERE o.status = 'Delivered'
),
cohort_progression AS (
    SELECT 
        com.cohort_month,
        com.order_month,
        (
            (CAST(SUBSTR(com.order_month, 1, 4) AS INTEGER) - CAST(SUBSTR(com.cohort_month, 1, 4) AS INTEGER)) * 12 +
            (CAST(SUBSTR(com.order_month, 6, 2) AS INTEGER) - CAST(SUBSTR(com.cohort_month, 6, 2) AS INTEGER))
        ) AS month_number,
        COUNT(DISTINCT com.user_id) AS active_customers
    FROM customer_orders_by_month com
    GROUP BY com.cohort_month, com.order_month
)
SELECT 
    cp.cohort_month,
    cs.cohort_customer_count AS cohort_size,
    cp.month_number,
    cp.active_customers,
    ROUND((cp.active_customers * 100.0) / cs.cohort_customer_count, 1) AS retention_rate_pct
FROM cohort_progression cp
JOIN cohort_size cs ON cp.cohort_month = cs.cohort_month
ORDER BY cp.cohort_month ASC, cp.month_number ASC;
