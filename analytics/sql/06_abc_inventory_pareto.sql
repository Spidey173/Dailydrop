-- =============================================================================
-- DailyDrop SQL Analytics Suite: 06. ABC Inventory Classification (Pareto 80/20 Rule)
-- Classifies catalog SKUs into Class A (Top 80% revenue), Class B (Next 15%),
-- and Class C (Tail 5%) for inventory optimization and stockout prevention.
-- =============================================================================

WITH product_sales AS (
    SELECT 
        oi.product_id,
        oi.product_name,
        oi.category,
        SUM(oi.quantity) AS units_sold,
        SUM(oi.line_subtotal) AS total_revenue,
        SUM(oi.gross_profit) AS total_gross_profit,
        ROUND(AVG(oi.unit_price), 2) AS selling_price
    FROM order_items oi
    JOIN orders o ON oi.order_id = o.order_id
    WHERE o.status = 'Delivered'
    GROUP BY oi.product_id, oi.product_name, oi.category
),
ranked_products AS (
    SELECT 
        product_id,
        product_name,
        category,
        units_sold,
        total_revenue,
        total_gross_profit,
        selling_price,
        SUM(total_revenue) OVER () AS overall_catalog_revenue,
        SUM(total_revenue) OVER (ORDER BY total_revenue DESC ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS cumulative_revenue,
        ROW_NUMBER() OVER (ORDER BY total_revenue DESC) AS sales_rank,
        COUNT(*) OVER () AS total_skus
    FROM product_sales
),
abc_classification AS (
    SELECT 
        product_id,
        product_name,
        category,
        sales_rank,
        units_sold,
        total_revenue,
        total_gross_profit,
        ROUND((total_revenue * 100.0) / overall_catalog_revenue, 2) AS revenue_share_pct,
        ROUND((cumulative_revenue * 100.0) / overall_catalog_revenue, 2) AS cumulative_revenue_pct,
        ROUND((sales_rank * 100.0) / total_skus, 2) AS cumulative_sku_pct,
        CASE 
            WHEN (cumulative_revenue * 100.0) / overall_catalog_revenue <= 80.0 THEN 'Class A (Critical Core: 80% Revenue)'
            WHEN (cumulative_revenue * 100.0) / overall_catalog_revenue <= 95.0 THEN 'Class B (Moderate Movers: 15% Revenue)'
            ELSE 'Class C (Slow Moving Tail: 5% Revenue)'
        END AS abc_class
    FROM ranked_products
)
SELECT 
    sales_rank,
    product_name,
    category,
    units_sold,
    total_revenue,
    total_gross_profit,
    revenue_share_pct,
    cumulative_revenue_pct,
    abc_class
FROM abc_classification
ORDER BY sales_rank ASC;
