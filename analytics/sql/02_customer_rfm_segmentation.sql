-- =============================================================================
-- DailyDrop SQL Analytics Suite: 02. Customer RFM Segmentation
-- Computes Recency, Frequency, and Monetary scores using NTILE(5) window functions
-- and classifies customers into actionable lifecycle cohorts.
-- Target Engine: Neon PostgreSQL
-- =============================================================================

WITH customer_aggregates AS (
    SELECT 
        o.user_id,
        o.full_name AS customer_name,
        COALESCE(o.city, 'Bangalore') AS city,
        COUNT(o.order_id) AS total_orders,
        SUM(o.total_amount) AS total_spend,
        ROUND(AVG(o.total_amount), 2) AS avg_basket_size,
        EXTRACT(DAY FROM ('2026-11-01'::timestamp - MAX(o.order_date)))::integer AS recency_days
    FROM orders o
    WHERE o.status = 'Delivered'
    GROUP BY o.user_id, o.full_name, o.city
),
rfm_scores AS (
    SELECT 
        user_id,
        customer_name,
        city,
        recency_days,
        total_orders,
        total_spend,
        avg_basket_size,
        NTILE(5) OVER (ORDER BY recency_days DESC) AS r_score,
        NTILE(5) OVER (ORDER BY total_orders ASC) AS f_score,
        NTILE(5) OVER (ORDER BY total_spend ASC) AS m_score
    FROM customer_aggregates
)
SELECT 
    user_id,
    customer_name,
    city,
    recency_days,
    total_orders,
    total_spend,
    avg_basket_size,
    r_score,
    f_score,
    m_score,
    (r_score::text || f_score::text || m_score::text) AS rfm_cell,
    ROUND((r_score + f_score + m_score) / 3.0, 2) AS avg_rfm_score,
    CASE 
        WHEN r_score >= 4 AND f_score >= 4 AND m_score >= 4 THEN 'Champions (VIP)'
        WHEN r_score >= 3 AND f_score >= 3 THEN 'Loyal Customers'
        WHEN r_score >= 4 AND f_score <= 2 THEN 'Recent / Promising'
        WHEN r_score <= 2 AND f_score >= 3 THEN 'At Risk (High Value Churn)'
        WHEN r_score <= 2 AND f_score <= 2 THEN 'Hibernating / Lost'
        ELSE 'Needs Attention'
    END AS customer_segment
FROM rfm_scores
ORDER BY total_spend DESC;
