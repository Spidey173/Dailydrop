-- =============================================================================
-- DailyDrop SQL Analytics Suite: 03. Customer Cohort Retention Analysis
-- Tracks repeat purchasing behavior by acquisition cohort month across time.
-- =============================================================================

WITH customer_first_purchase AS (
    SELECT 
        customer_id,
        MIN(SUBSTR(order_date, 1, 7)) AS cohort_month
    FROM orders
    WHERE status = 'Delivered'
    GROUP BY customer_id
),
cohort_size AS (
    SELECT 
        cohort_month,
        COUNT(DISTINCT customer_id) AS cohort_customer_count
    FROM customer_first_purchase
    GROUP BY cohort_month
),
customer_orders_by_month AS (
    SELECT DISTINCT
        o.customer_id,
        fp.cohort_month,
        SUBSTR(o.order_date, 1, 7) AS order_month
    FROM orders o
    JOIN customer_first_purchase fp ON o.customer_id = fp.customer_id
    WHERE o.status = 'Delivered'
),
cohort_progression AS (
    SELECT 
        com.cohort_month,
        com.order_month,
        -- Calculate month offset (Month 0, Month 1, Month 2...)
        (
            (CAST(SUBSTR(com.order_month, 1, 4) AS INTEGER) - CAST(SUBSTR(com.cohort_month, 1, 4) AS INTEGER)) * 12 +
            (CAST(SUBSTR(com.order_month, 6, 2) AS INTEGER) - CAST(SUBSTR(com.cohort_month, 6, 2) AS INTEGER))
        ) AS month_number,
        COUNT(DISTINCT com.customer_id) AS active_customers
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
