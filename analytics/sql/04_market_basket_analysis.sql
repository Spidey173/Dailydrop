-- =============================================================================
-- DailyDrop SQL Analytics Suite: 04. Market Basket Analysis & Product Affinities
-- Identifies items frequently co-purchased together in the same cart transaction.
-- Target Engine: Neon PostgreSQL
-- =============================================================================

WITH order_pairs AS (
    SELECT 
        oi1.order_id,
        oi1.product_id AS product_a_id,
        oi1.product_name AS product_a_name,
        p1.category AS category_a,
        oi2.product_id AS product_b_id,
        oi2.product_name AS product_b_name,
        p2.category AS category_b
    FROM order_items oi1
    JOIN products p1 ON oi1.product_id = p1.product_id
    JOIN order_items oi2 
        ON oi1.order_id = oi2.order_id 
        AND oi1.product_id < oi2.product_id
    JOIN products p2 ON oi2.product_id = p2.product_id
),
total_orders_count AS (
    SELECT COUNT(DISTINCT order_id) AS total_orders FROM orders WHERE status = 'Delivered'
),
pair_frequencies AS (
    SELECT 
        product_a_name,
        category_a,
        product_b_name,
        category_b,
        COUNT(DISTINCT order_id) AS times_bought_together
    FROM order_pairs
    GROUP BY product_a_name, category_a, product_b_name, category_b
)
SELECT 
    pf.product_a_name,
    pf.category_a,
    pf.product_b_name,
    pf.category_b,
    pf.times_bought_together,
    ROUND((pf.times_bought_together * 100.0) / toc.total_orders, 2) AS pair_support_pct,
    CASE 
        WHEN pf.category_a = pf.category_b THEN 'Within-Category Affinity'
        ELSE 'Cross-Category Bundle'
    END AS affinity_type
FROM pair_frequencies pf
CROSS JOIN total_orders_count toc
WHERE pf.times_bought_together >= 5
ORDER BY pf.times_bought_together DESC
LIMIT 50;
