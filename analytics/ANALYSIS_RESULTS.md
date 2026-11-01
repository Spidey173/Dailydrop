# 🛒 DailyDrop E-Commerce & Quick-Commerce Data Analytics Report

Generated on 2026-11-01 18:55:51 using **Neon PostgreSQL** cloud engine.

### 📈 Executive Revenue & Monthly MoM Growth KPIs

```sql
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
        sales_month,
        total_orders,
        active_customers,
        monthly_gmv,
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
    average_order_value,
    COALESCE(
        ROUND(((monthly_gmv - prev_month_gmv) / prev_month_gmv) * 100.0, 2), 
        0.0
    ) AS mom_growth_pct,
    cumulative_gmv
FROM mom_growth
ORDER BY sales_month ASC
```

| sales_month | total_orders | active_customers | monthly_gmv | average_order_value | mom_growth_pct | cumulative_gmv |
| ----------- | ------------ | ---------------- | ----------- | ------------------- | -------------- | -------------- |
| 2025-11     | 5            | 2                | 1738.00     | 347.60              | 0.0            | 1738.00        |
| 2025-12     | 38           | 11               | 24944.00    | 656.42              | 1335.21        | 26682.00       |
| 2026-01     | 62           | 19               | 28514.00    | 459.90              | 14.31          | 55196.00       |
| 2026-02     | 101          | 35               | 48148.00    | 476.71              | 68.86          | 103344.00      |
| 2026-03     | 149          | 50               | 82506.00    | 553.73              | 71.36          | 185850.00      |
| 2026-04     | 188          | 62               | 107328.00   | 570.89              | 30.09          | 293178.00      |
| 2026-05     | 252          | 81               | 134829.00   | 535.04              | 25.62          | 428007.00      |
| 2026-06     | 296          | 95               | 153237.00   | 517.69              | 13.65          | 581244.00      |
| 2026-07     | 414          | 123              | 199492.00   | 481.86              | 30.19          | 780736.00      |
| 2026-08     | 475          | 142              | 241412.00   | 508.24              | 21.01          | 1022148.00     |
| 2026-09     | 554          | 161              | 279985.40   | 505.39              | 15.98          | 1302133.40     |
| 2026-10     | 674          | 198              | 352181.00   | 522.52              | 25.79          | 1654314.40     |

### 🎯 Customer RFM Segmentation & Lifecycle Clusters

```sql
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
ORDER BY total_spend DESC
```

| user_id | customer_name   | city      | recency_days | total_orders | total_spend | avg_basket_size | r_score | f_score | m_score | rfm_cell | avg_rfm_score | customer_segment           |
| ------- | --------------- | --------- | ------------ | ------------ | ----------- | --------------- | ------- | ------- | ------- | -------- | ------------- | -------------------------- |
| 596     | Ritu Banerjee   | Bangalore | 4            | 73           | 39564.00    | 541.97          | 4       | 5       | 5       | 455      | 4.67          | Champions (VIP)            |
| 637     | Ananya Nair     | Bangalore | 1            | 56           | 31445.00    | 561.52          | 5       | 5       | 5       | 555      | 5.00          | Champions (VIP)            |
| 619     | Sneha Nair      | Bangalore | 8            | 61           | 29428.00    | 482.43          | 3       | 5       | 5       | 355      | 4.33          | Loyal Customers            |
| 491     | Prisha Kulkarni | Hyderabad | 1            | 61           | 29363.00    | 481.36          | 5       | 5       | 5       | 555      | 5.00          | Champions (VIP)            |
| 644     | Pooja Menon     | Bangalore | 1            | 60           | 29266.00    | 487.77          | 5       | 5       | 5       | 555      | 5.00          | Champions (VIP)            |
| 561     | Shweta Chopra   | Bangalore | 1            | 60           | 26988.00    | 449.80          | 5       | 5       | 5       | 555      | 5.00          | Champions (VIP)            |
| 713     | Sunita Reddy    | Delhi NCR | 0            | 47           | 25973.00    | 552.62          | 5       | 5       | 5       | 555      | 5.00          | Champions (VIP)            |
| 507     | Vikram Iyer     | Delhi NCR | 0            | 47           | 25014.00    | 532.21          | 5       | 5       | 5       | 555      | 5.00          | Champions (VIP)            |
| 515     | Arjun Mehta     | Delhi NCR | 5            | 46           | 24580.00    | 534.35          | 4       | 5       | 5       | 455      | 4.67          | Champions (VIP)            |
| 719     | Ritu Deshmukh   | Bangalore | 10           | 26           | 24493.00    | 942.04          | 3       | 5       | 5       | 355      | 4.33          | Loyal Customers            |
| 608     | Rahul Joshi     | Mumbai    | 3            | 38           | 23463.00    | 617.45          | 4       | 5       | 5       | 455      | 4.67          | Champions (VIP)            |
| 714     | Pari Nair       | Delhi NCR | 3            | 42           | 22293.00    | 530.79          | 4       | 5       | 5       | 455      | 4.67          | Champions (VIP)            |
| 660     | Rahul Bhat      | Pune      | 12           | 42           | 21901.00    | 521.45          | 2       | 5       | 5       | 255      | 4.00          | At Risk (High Value Churn) |
| 691     | Rajesh Mehta    | Mumbai    | 1            | 38           | 21664.00    | 570.11          | 5       | 5       | 5       | 555      | 5.00          | Champions (VIP)            |
| 722     | Sunita Agarwal  | Mumbai    | 2            | 22           | 21252.00    | 966.00          | 4       | 5       | 5       | 455      | 4.67          | Champions (VIP)            |

### 🔄 Monthly Cohort Retention Heatmap Analysis

```sql
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
ORDER BY cp.cohort_month ASC, cp.month_number ASC
```

| cohort_month | cohort_size | month_number | active_customers | retention_rate_pct |
| ------------ | ----------- | ------------ | ---------------- | ------------------ |
| 2025-11      | 2           | 0            | 2                | 100.0              |
| 2025-11      | 2           | 1            | 2                | 100.0              |
| 2025-11      | 2           | 2            | 2                | 100.0              |
| 2025-11      | 2           | 3            | 2                | 100.0              |
| 2025-11      | 2           | 4            | 2                | 100.0              |
| 2025-11      | 2           | 5            | 2                | 100.0              |
| 2025-11      | 2           | 6            | 2                | 100.0              |
| 2025-11      | 2           | 7            | 2                | 100.0              |
| 2025-11      | 2           | 8            | 2                | 100.0              |
| 2025-11      | 2           | 9            | 2                | 100.0              |
| 2025-11      | 2           | 10           | 2                | 100.0              |
| 2025-11      | 2           | 11           | 2                | 100.0              |
| 2025-12      | 9           | 0            | 9                | 100.0              |
| 2025-12      | 9           | 1            | 6                | 66.7               |
| 2025-12      | 9           | 2            | 8                | 88.9               |

### 🛒 Market Basket Analysis & Product Co-Purchases

```sql
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
LIMIT 50
```

| product_a_name                          | category_a          | product_b_name                          | category_b          | times_bought_together | pair_support_pct | affinity_type            |
| --------------------------------------- | ------------------- | --------------------------------------- | ------------------- | --------------------- | ---------------- | ------------------------ |
| Pepsi Refreshing Soda Can (300 ml)      | Beverages           | Sprite Clear Lemon-Lime Bottle (750 ml) | Beverages           | 17                    | 0.53             | Within-Category Affinity |
| Cavin's Badam Flavoured Milk (200 ml)   | Beverages           | Sting Energy Drink Pet Bottle (250 ml)  | Beverages           | 17                    | 0.53             | Within-Category Affinity |
| Coca-Cola Refreshing Soda Can (300 ml)  | Beverages           | Fanta Orange Soda Bottle (750 ml)       | Beverages           | 17                    | 0.53             | Within-Category Affinity |
| Fresh Mango Sweet Lassi (250 ml)        | Beverages           | Sprite Lemon & Lime Can (300 ml)        | Beverages           | 16                    | 0.50             | Within-Category Affinity |
| Amul Rose Flavour Sweet Lassi (200 ml)  | Beverages           | Real Lychee Fruit Lassi (200 ml)        | Beverages           | 16                    | 0.50             | Within-Category Affinity |
| Coca-Cola Refreshing Soda Can (300 ml)  | Beverages           | Sprite Clear Lemon-Lime Bottle (750 ml) | Beverages           | 15                    | 0.47             | Within-Category Affinity |
| Cavin's Badam Flavoured Milk (200 ml)   | Beverages           | Sprite Clear Lemon-Lime Bottle (750 ml) | Beverages           | 15                    | 0.47             | Within-Category Affinity |
| Cavin's Badam Flavoured Milk (200 ml)   | Beverages           | Pepsi Cola Soft Drink Bottle (750 ml)   | Beverages           | 15                    | 0.47             | Within-Category Affinity |
| Amul Rose Flavour Sweet Lassi (200 ml)  | Beverages           | Fanta Orange Soda Bottle (750 ml)       | Beverages           | 14                    | 0.44             | Within-Category Affinity |
| Fresh White Cauliflower (1 pc, ~600 g)  | Fruits & Vegetables | Imported Crisp Green Apples (500 g)     | Fruits & Vegetables | 13                    | 0.41             | Within-Category Affinity |
| Real Lychee Fruit Lassi (200 ml)        | Beverages           | Sprite Lemon & Lime Can (300 ml)        | Beverages           | 13                    | 0.41             | Within-Category Affinity |
| Coca-Cola Refreshing Soda Can (300 ml)  | Beverages           | Govind Sweet Creamy Lassi (200 ml)      | Beverages           | 13                    | 0.41             | Within-Category Affinity |
| Pepsi Refreshing Soda Can (300 ml)      | Beverages           | Sprite Lemon & Lime Can (300 ml)        | Beverages           | 13                    | 0.41             | Within-Category Affinity |
| Sprite Clear Lemon-Lime Bottle (750 ml) | Beverages           | Sting Energy Drink Pet Bottle (250 ml)  | Beverages           | 13                    | 0.41             | Within-Category Affinity |
| Pepsi Cola Soft Drink Bottle (750 ml)   | Beverages           | Sprite Clear Lemon-Lime Bottle (750 ml) | Beverages           | 13                    | 0.41             | Within-Category Affinity |

### ⚡ Quick-Commerce 10-Minute SLA & Hourly Rush Analysis

```sql
WITH hourly_orders AS (
    SELECT 
        EXTRACT(HOUR FROM order_date)::integer AS hour_of_day,
        order_id,
        total_amount,
        COALESCE(delivery_duration_minutes, 7.2) AS delivery_duration_minutes
    FROM orders
    WHERE status = 'Delivered'
)
SELECT 
    hour_of_day,
    CASE 
        WHEN hour_of_day BETWEEN 7 AND 10 THEN 'Morning Rush (Breakfast)'
        WHEN hour_of_day BETWEEN 12 AND 15 THEN 'Afternoon Lull'
        WHEN hour_of_day BETWEEN 17 AND 21 THEN 'Evening Rush (Dinner/Snacks)'
        ELSE 'Late Night / Early Morning'
    END AS operational_window,
    COUNT(order_id) AS total_orders,
    ROUND(SUM(total_amount), 2) AS total_revenue,
    ROUND(AVG(delivery_duration_minutes), 2) AS avg_delivery_minutes,
    SUM(CASE WHEN delivery_duration_minutes > 10.0 THEN 1 ELSE 0 END) AS sla_breaches,
    ROUND(
        (SUM(CASE WHEN delivery_duration_minutes > 10.0 THEN 1.0 ELSE 0.0 END) / COUNT(order_id)) * 100.0, 
        2
    ) AS sla_breach_rate_pct
FROM hourly_orders
GROUP BY hour_of_day
ORDER BY hour_of_day ASC
```

| hour_of_day | operational_window           | total_orders | total_revenue | avg_delivery_minutes | sla_breaches | sla_breach_rate_pct |
| ----------- | ---------------------------- | ------------ | ------------- | -------------------- | ------------ | ------------------- |
| 7           | Morning Rush (Breakfast)     | 564          | 288384.00     | 7.28                 | 16           | 2.84                |
| 8           | Morning Rush (Breakfast)     | 520          | 276323.00     | 7.21                 | 8            | 1.54                |
| 9           | Morning Rush (Breakfast)     | 564          | 291448.00     | 7.24                 | 11           | 1.95                |
| 10          | Morning Rush (Breakfast)     | 582          | 310802.00     | 7.17                 | 8            | 1.37                |
| 11          | Late Night / Early Morning   | 22           | 22728.00      | 7.55                 | 1            | 4.55                |
| 12          | Afternoon Lull               | 30           | 30094.40      | 7.28                 | 0            | 0.00                |
| 13          | Afternoon Lull               | 22           | 28828.00      | 6.90                 | 0            | 0.00                |
| 14          | Afternoon Lull               | 27           | 21659.00      | 7.20                 | 0            | 0.00                |
| 15          | Afternoon Lull               | 27           | 29810.00      | 7.52                 | 1            | 3.70                |
| 16          | Late Night / Early Morning   | 17           | 18202.00      | 6.86                 | 1            | 5.88                |
| 17          | Evening Rush (Dinner/Snacks) | 167          | 60295.00      | 7.28                 | 6            | 3.59                |
| 18          | Evening Rush (Dinner/Snacks) | 172          | 61828.00      | 7.48                 | 8            | 4.65                |
| 19          | Evening Rush (Dinner/Snacks) | 160          | 69256.00      | 7.17                 | 1            | 0.63                |
| 20          | Evening Rush (Dinner/Snacks) | 169          | 75222.00      | 7.39                 | 3            | 1.78                |
| 21          | Evening Rush (Dinner/Snacks) | 161          | 68025.00      | 7.01                 | 0            | 0.00                |

### ⚡ Quick-Commerce 10-Minute SLA & Hourly Rush Analysis

```sql
SELECT 
    COALESCE(city, 'Bangalore') AS city,
    COUNT(order_id) AS total_deliveries,
    ROUND(AVG(total_amount), 2) AS aov,
    ROUND(AVG(COALESCE(delivery_duration_minutes, 7.2)), 2) AS avg_delivery_time_mins,
    ROUND(MIN(COALESCE(delivery_duration_minutes, 7.2)), 2) AS fastest_delivery_mins,
    ROUND(MAX(COALESCE(delivery_duration_minutes, 7.2)), 2) AS slowest_delivery_mins,
    ROUND(
        (SUM(CASE WHEN COALESCE(delivery_duration_minutes, 7.2) <= 10.0 THEN 1.0 ELSE 0.0 END) / COUNT(order_id)) * 100.0, 
        1
    ) AS on_time_sla_adherence_pct
FROM orders
WHERE status = 'Delivered'
GROUP BY COALESCE(city, 'Bangalore')
ORDER BY total_deliveries DESC
```

| city      | total_deliveries | aov    | avg_delivery_time_mins | fastest_delivery_mins | slowest_delivery_mins | on_time_sla_adherence_pct |
| --------- | ---------------- | ------ | ---------------------- | --------------------- | --------------------- | ------------------------- |
| Bangalore | 1179             | 493.79 | 7.24                   | 3.50                  | 12.60                 | 98.3                      |
| Delhi NCR | 753              | 496.82 | 7.21                   | 3.50                  | 11.60                 | 98.0                      |
| Mumbai    | 591              | 558.24 | 7.25                   | 3.50                  | 10.70                 | 98.6                      |
| Hyderabad | 419              | 513.03 | 7.28                   | 3.50                  | 10.90                 | 96.9                      |
| Pune      | 266              | 575.76 | 7.22                   | 3.50                  | 12.70                 | 97.0                      |

### 📦 ABC Inventory Classification (Pareto 80/20 Rule)

```sql
WITH product_sales AS (
    SELECT 
        oi.product_id,
        oi.product_name,
        p.category,
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
        product_id,
        product_name,
        category,
        units_sold,
        total_revenue,
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
    revenue_share_pct,
    cumulative_revenue_pct,
    abc_class
FROM abc_classification
ORDER BY sales_rank ASC
```

| sales_rank | product_name                                     | category            | units_sold | total_revenue | revenue_share_pct | cumulative_revenue_pct | abc_class                            |
| ---------- | ------------------------------------------------ | ------------------- | ---------- | ------------- | ----------------- | ---------------------- | ------------------------------------ |
| 1          | Nutella Hazelnut Cocoa Spread (350 g)            | Snacks              | 132        | 42240.00      | 2.65              | 2.65                   | Class A (Critical Core: 80% Revenue) |
| 2          | Amul Pure Cow Ghee (500 ml)                      | Dairy & Breakfast   | 112        | 36400.00      | 2.29              | 4.94                   | Class A (Critical Core: 80% Revenue) |
| 3          | Royal Gala Fresh Apples (1 kg)                   | Fruits & Vegetables | 196        | 31360.00      | 1.97              | 6.91                   | Class A (Critical Core: 80% Revenue) |
| 4          | Brooke Bond Red Label Strong Tea (500 g)         | Dairy & Breakfast   | 114        | 29640.00      | 1.86              | 8.77                   | Class A (Critical Core: 80% Revenue) |
| 5          | Imported Crisp Green Apples (500 g)              | Fruits & Vegetables | 238        | 28560.00      | 1.79              | 10.57                  | Class A (Critical Core: 80% Revenue) |
| 6          | M.A.C Studio Fix Fluid SPF 15 Foundation (30 ml) | Personal Care       | 25         | 24975.00      | 1.57              | 12.14                  | Class A (Critical Core: 80% Revenue) |
| 7          | Cadbury Bournvita Health Drink (500 g)           | Dairy & Breakfast   | 104        | 24440.00      | 1.54              | 13.67                  | Class A (Critical Core: 80% Revenue) |
| 8          | Organic Blueberry Cinnamon Flax Cereal (300 g)   | Dairy & Breakfast   | 106        | 23320.00      | 1.47              | 15.14                  | Class A (Critical Core: 80% Revenue) |
| 9          | Horlicks Classic Malt Nutrition Drink (500 g)    | Dairy & Breakfast   | 92         | 22540.00      | 1.42              | 16.56                  | Class A (Critical Core: 80% Revenue) |
| 10         | M.A.C Prep + Prime Natural Radiance Base (50 ml) | Personal Care       | 27         | 21573.00      | 1.36              | 17.91                  | Class A (Critical Core: 80% Revenue) |
| 11         | Kellogg's Choco Krispies Cereal (350 g)          | Dairy & Breakfast   | 122        | 21350.00      | 1.34              | 19.25                  | Class A (Critical Core: 80% Revenue) |
| 12         | Nutella Hazelnut Cocoa Spread (180 g)            | Dairy & Breakfast   | 107        | 20330.00      | 1.28              | 20.53                  | Class A (Critical Core: 80% Revenue) |
| 13         | Kellogg's Coco Pops Crunchy Cereal (375 g)       | Dairy & Breakfast   | 105        | 19425.00      | 1.22              | 21.75                  | Class A (Critical Core: 80% Revenue) |
| 14         | Almond & Nut Butter Spread (200 g)               | Dairy & Breakfast   | 94         | 18706.00      | 1.18              | 22.93                  | Class A (Critical Core: 80% Revenue) |
| 15         | Fresh Ruby Red Pomegranate (500 g)               | Fruits & Vegetables | 196        | 18620.00      | 1.17              | 24.10                  | Class A (Critical Core: 80% Revenue) |

