-- =============================================================================
-- DailyDrop SQL Analytics Suite: 05. Quick-Commerce Dispatch & 10-Minute SLA Adherence
-- Analyzes hourly order volume intensity, delivery duration distribution,
-- and SLA breach rates across operational hours and metropolitan hubs.
-- =============================================================================

-- Part A: Hourly Rush Analysis (Staffing & Dark Store Capacity Planning)
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
FROM orders
WHERE status = 'Delivered'
GROUP BY hour_of_day
ORDER BY hour_of_day ASC;

-- Part B: City-Level Delivery Performance
SELECT 
    city,
    COUNT(order_id) AS total_deliveries,
    ROUND(AVG(total_amount), 2) AS aov,
    ROUND(AVG(delivery_duration_minutes), 2) AS avg_delivery_time_mins,
    ROUND(MIN(delivery_duration_minutes), 2) AS fastest_delivery_mins,
    ROUND(MAX(delivery_duration_minutes), 2) AS slowest_delivery_mins,
    ROUND(
        (SUM(CASE WHEN delivery_duration_minutes <= 10.0 THEN 1.0 ELSE 0.0 END) / COUNT(order_id)) * 100.0, 
        1
    ) AS on_time_sla_adherence_pct
FROM orders
WHERE status = 'Delivered'
GROUP BY city
ORDER BY total_deliveries DESC;
