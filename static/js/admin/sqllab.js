/**
 * Admin Dashboard SQL Analytics Lab Modal Controller
 */
        // ====================================================================
        // SQL ANALYTICS LAB MODAL CONTROLLER
        // ====================================================================
        const SQL_QUERIES = {
            rfm: `-- 01. Customer RFM Segmentation using NTILE(5) Window Functions
WITH customer_aggregates AS (
    SELECT 
        o.user_id,
        o.full_name AS customer_name,
        COALESCE(o.city, 'Bangalore') AS city,
        COUNT(o.order_id) AS total_orders,
        SUM(o.total_amount) AS total_spend,
        ROUND(AVG(o.total_amount), 2) AS avg_basket_size,
        EXTRACT(DAY FROM (CURRENT_TIMESTAMP - MAX(o.order_date)))::integer AS recency_days
    FROM orders o
    WHERE o.status = 'Delivered'
    GROUP BY o.user_id, o.full_name, o.city
),
rfm_scores AS (
    SELECT 
        user_id, customer_name, city, recency_days, total_orders, total_spend, avg_basket_size,
        NTILE(5) OVER (ORDER BY recency_days DESC) AS r_score,
        NTILE(5) OVER (ORDER BY total_orders ASC) AS f_score,
        NTILE(5) OVER (ORDER BY total_spend ASC) AS m_score
    FROM customer_aggregates
)
SELECT 
    user_id, customer_name, city, recency_days, total_orders, total_spend, avg_basket_size,
    r_score, f_score, m_score, (r_score::text || f_score::text || m_score::text) AS rfm_cell,
    CASE 
        WHEN r_score >= 4 AND f_score >= 4 AND m_score >= 4 THEN 'Champions (VIP)'
        WHEN r_score >= 3 AND f_score >= 3 THEN 'Loyal Customers'
        WHEN r_score >= 4 AND f_score <= 2 THEN 'Recent / Promising'
        WHEN r_score <= 2 AND f_score >= 3 THEN 'At Risk (High Value Churn)'
        WHEN r_score <= 2 AND f_score <= 2 THEN 'Hibernating / Lost'
        ELSE 'Needs Attention'
    END AS customer_segment
FROM rfm_scores
ORDER BY total_spend DESC;`,

            mom: `-- 02. Executive MoM Revenue Growth with LAG() Analytic Window Function
WITH monthly_sales AS (
    SELECT 
        TO_CHAR(order_date, 'YYYY-MM') AS sales_month,
        COUNT(DISTINCT order_id) AS total_orders,
        COUNT(DISTINCT user_id) AS active_customers,
        SUM(total_amount) AS monthly_gmv,
        ROUND(AVG(total_amount), 2) AS average_order_value
    FROM orders
    WHERE status = 'Delivered'
    GROUP BY TO_CHAR(order_date, 'YYYY-MM')
),
mom_growth AS (
    SELECT 
        sales_month, total_orders, active_customers, monthly_gmv, average_order_value,
        LAG(monthly_gmv, 1) OVER (ORDER BY sales_month) AS prev_month_gmv,
        SUM(monthly_gmv) OVER (ORDER BY sales_month ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS cumulative_gmv
    FROM monthly_sales
)
SELECT 
    sales_month, total_orders, active_customers, monthly_gmv, average_order_value,
    COALESCE(ROUND(((monthly_gmv - prev_month_gmv) / prev_month_gmv) * 100.0, 2), 0.0) AS mom_growth_pct,
    cumulative_gmv
FROM mom_growth
ORDER BY sales_month ASC;`,

            pareto: `-- 03. Pareto ABC Inventory Stratification (80/20 Rule)
WITH product_sales AS (
    SELECT 
        oi.product_id, oi.product_name, p.category,
        SUM(oi.quantity) AS units_sold,
        SUM(oi.subtotal) AS total_revenue,
        ROUND(AVG(oi.price), 2) AS selling_price
    FROM order_items oi
    JOIN orders o ON oi.order_id = o.order_id
    JOIN products p ON oi.product_id = p.product_id
    WHERE o.status = 'Delivered'
    GROUP BY oi.product_id, oi.product_name, p.category
),
ranked_products AS (
    SELECT 
        product_id, product_name, category, units_sold, total_revenue, selling_price,
        SUM(total_revenue) OVER () AS overall_catalog_revenue,
        SUM(total_revenue) OVER (ORDER BY total_revenue DESC ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS cumulative_revenue,
        ROW_NUMBER() OVER (ORDER BY total_revenue DESC) AS sales_rank,
        COUNT(*) OVER () AS total_skus
    FROM product_sales
)
SELECT 
    sales_rank, product_name, category, units_sold, total_revenue,
    ROUND((total_revenue * 100.0) / overall_catalog_revenue, 2) AS revenue_share_pct,
    ROUND((cumulative_revenue * 100.0) / overall_catalog_revenue, 2) AS cumulative_revenue_pct,
    CASE 
        WHEN (cumulative_revenue * 100.0) / overall_catalog_revenue <= 80.0 THEN 'Class A (Critical Core: 80% Revenue)'
        WHEN (cumulative_revenue * 100.0) / overall_catalog_revenue <= 95.0 THEN 'Class B (Moderate Movers: 15% Revenue)'
        ELSE 'Class C (Slow Moving Tail: 5% Revenue)'
    END AS abc_class
FROM ranked_products
ORDER BY sales_rank ASC;`,

            basket: `-- 04. Market Basket Pairwise Affinity Analysis (Self-Join Optimization)
WITH order_pairs AS (
    SELECT 
        oi1.order_id,
        oi1.product_name AS product_a_name, p1.category AS category_a,
        oi2.product_name AS product_b_name, p2.category AS category_b
    FROM order_items oi1
    JOIN products p1 ON oi1.product_id = p1.product_id
    JOIN order_items oi2 
        ON oi1.order_id = oi2.order_id 
        AND oi1.product_id < oi2.product_id -- Prevents Cartesian duplication
    JOIN products p2 ON oi2.product_id = p2.product_id
),
total_orders_count AS (
    SELECT COUNT(DISTINCT order_id) AS total_orders FROM orders WHERE status = 'Delivered'
),
pair_frequencies AS (
    SELECT 
        product_a_name, category_a, product_b_name, category_b,
        COUNT(DISTINCT order_id) AS times_bought_together
    FROM order_pairs
    GROUP BY product_a_name, category_a, product_b_name, category_b
)
SELECT 
    pf.product_a_name, pf.category_a, pf.product_b_name, pf.category_b,
    pf.times_bought_together,
    ROUND((pf.times_bought_together * 100.0) / toc.total_orders, 2) AS pair_support_pct,
    CASE WHEN pf.category_a = pf.category_b THEN 'Within-Category Affinity' ELSE 'Cross-Category Bundle' END AS affinity_type
FROM pair_frequencies pf
CROSS JOIN total_orders_count toc
WHERE pf.times_bought_together >= 5
ORDER BY pf.times_bought_together DESC
LIMIT 50;`,

            cohort: `-- 05. Customer Monthly Cohort Retention Matrix
WITH customer_first_purchase AS (
    SELECT user_id, MIN(TO_CHAR(order_date, 'YYYY-MM')) AS cohort_month
    FROM orders WHERE status = 'Delivered' GROUP BY user_id
),
cohort_size AS (
    SELECT cohort_month, COUNT(DISTINCT user_id) AS cohort_customer_count
    FROM customer_first_purchase GROUP BY cohort_month
),
customer_orders_by_month AS (
    SELECT DISTINCT o.user_id, fp.cohort_month, TO_CHAR(o.order_date, 'YYYY-MM') AS order_month
    FROM orders o JOIN customer_first_purchase fp ON o.user_id = fp.user_id WHERE o.status = 'Delivered'
),
cohort_progression AS (
    SELECT 
        com.cohort_month, com.order_month,
        ((CAST(SUBSTR(com.order_month, 1, 4) AS INTEGER) - CAST(SUBSTR(com.cohort_month, 1, 4) AS INTEGER)) * 12 +
         (CAST(SUBSTR(com.order_month, 6, 2) AS INTEGER) - CAST(SUBSTR(com.cohort_month, 6, 2) AS INTEGER))) AS month_number,
        COUNT(DISTINCT com.user_id) AS active_customers
    FROM customer_orders_by_month com GROUP BY com.cohort_month, com.order_month
)
SELECT 
    cp.cohort_month, cs.cohort_customer_count AS cohort_size, cp.month_number, cp.active_customers,
    ROUND((cp.active_customers * 100.0) / cs.cohort_customer_count, 1) AS retention_rate_pct
FROM cohort_progression cp JOIN cohort_size cs ON cp.cohort_month = cs.cohort_month
ORDER BY cp.cohort_month ASC, cp.month_number ASC;`
        };

        function openSqlLabModal() {
            document.getElementById('sqlLabModal').classList.add('active');
        }

        function closeSqlLabModal() {
            document.getElementById('sqlLabModal').classList.remove('active');
        }

        function showSqlQuery(queryKey) {
            document.querySelectorAll('.sql-tab-btn').forEach(b => b.classList.remove('active'));
            const clickedBtn = event ? event.target : null;
            if (clickedBtn && clickedBtn.classList) clickedBtn.classList.add('active');
            
            const codeEl = document.getElementById('sqlCodeContainer');
            if (codeEl) {
                codeEl.textContent = SQL_QUERIES[queryKey] || '-- Query not found';
            }
        }
