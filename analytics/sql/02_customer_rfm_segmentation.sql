-- =============================================================================
-- DailyDrop SQL Analytics Suite: 02. Customer RFM Segmentation
-- Computes Recency, Frequency, and Monetary scores using NTILE(5) window functions
-- and classifies customers into actionable lifecycle cohorts.
-- =============================================================================

WITH customer_aggregates AS (
    SELECT 
        customer_id,
        customer_name,
        customer_email,
        city,
        COUNT(order_id) AS total_orders,
        SUM(total_amount) AS total_spend,
        ROUND(AVG(total_amount), 2) AS avg_basket_size,
        -- Calculate days since last order relative to end of dataset
        CAST(ROUND(JULIANDAY('2026-11-01') - JULIANDAY(MAX(order_date))) AS INTEGER) AS recency_days
    FROM orders
    WHERE status = 'Delivered'
    GROUP BY customer_id, customer_name, customer_email, city
),
rfm_scores AS (
    SELECT 
        customer_id,
        customer_name,
        customer_email,
        city,
        recency_days,
        total_orders,
        total_spend,
        avg_basket_size,
        -- Recency: Lower days = higher score (5 is best)
        NTILE(5) OVER (ORDER BY recency_days DESC) AS r_score,
        -- Frequency & Monetary: Higher count/spend = higher score (5 is best)
        NTILE(5) OVER (ORDER BY total_orders ASC) AS f_score,
        NTILE(5) OVER (ORDER BY total_spend ASC) AS m_score
    FROM customer_aggregates
)
SELECT 
    customer_id,
    customer_name,
    city,
    recency_days,
    total_orders,
    total_spend,
    avg_basket_size,
    r_score,
    f_score,
    m_score,
    (r_score || f_score || m_score) AS rfm_cell,
    ROUND((r_score + f_score + m_score) / 3.0, 2) AS avg_rfm_score,
    CASE 
        WHEN r_score >= 4 AND f_score >= 4 AND m_score >= 4 THEN 'Champions (VIP)'
        WHEN r_score >= 3 AND f_score >= 3 THEN 'Loyal Customers'
        WHEN r_score >= 4 AND f_score <= 2 THEN 'Recent Promising'
        WHEN r_score = 3 AND f_score <= 2 THEN 'Needs Attention'
        WHEN r_score <= 2 AND f_score >= 3 THEN 'At Risk (High Value Churn)'
        WHEN r_score <= 2 AND f_score <= 2 AND m_score >= 3 THEN 'About to Sleep'
        ELSE 'Hibernating / Lost'
    END AS customer_segment
FROM rfm_scores
ORDER BY total_spend DESC;
