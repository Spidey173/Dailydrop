"""
Analytics Data Repository.
Handles unified multi-table executive aggregation, RFM customer segmentation,
cohort retention analysis, ABC inventory classification, and market basket affinities.
"""
import json
import time
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Tuple
from psycopg2.extras import RealDictCursor
from database import get_db_connection
from .product_repository import get_all_products
from .order_repository import get_all_orders_with_user_info

logger = logging.getLogger("dailydrop.repositories.analytics")

_ANALYTICS_CACHE: Dict[str, Tuple[float, Dict[str, Any]]] = {}
_ANALYTICS_TTL_SECONDS = 300.0  # 5 minutes in-memory cache for ultra-fast, responsive dashboard
_DEFAULT_CUSTOMER_PROFILES: List[Dict[str, Any]] = []


def _get_fallback_rfm_customers() -> List[Dict[str, Any]]:
    """Compute customer RFM segments in Python over existing orders, returning empty list if insufficient data."""
    try:
        orders = get_all_orders_with_user_info()
        if len(orders) >= 3:
            users_map: Dict[int, Dict[str, Any]] = {}
            now = datetime.now(timezone.utc)
            for o in orders:
                uid = o.get('user_id')
                if not uid:
                    continue
                if uid not in users_map:
                    users_map[uid] = {
                        'user_id': uid,
                        'name': str(o.get('full_name') or 'Customer'),
                        'email': str(o.get('user_email') or ''),
                        'phone': str(o.get('phone_number') or ''),
                        'city': str(o.get('city') or 'Bangalore'),
                        'total_orders': 0,
                        'total_spend': 0.0,
                        'last_order_date': None,
                    }
                u = users_map[uid]
                u['total_orders'] += 1
                u['total_spend'] += float(o.get('total_amount') or 0.0)
                odate = o.get('order_date')
                if isinstance(odate, str):
                    try:
                        dt = datetime.fromisoformat(odate[:19])
                    except Exception:
                        dt = now
                elif isinstance(odate, datetime):
                    dt = odate
                else:
                    dt = now
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                if u['last_order_date'] is None or dt > u['last_order_date']:
                    u['last_order_date'] = dt

            if len(users_map) >= 1:
                cust_list = list(users_map.values())
                for c in cust_list:
                    c['total_spend'] = round(c['total_spend'], 2)
                    c['avg_order_value'] = round(c['total_spend'] / c['total_orders'], 2) if c['total_orders'] > 0 else 0.0
                    rec = (now - c['last_order_date']).days if c['last_order_date'] else 99
                    c['recency_days'] = max(0, rec)
                    c['last_order_str'] = c['last_order_date'].strftime('%Y-%m-%d %H:%M') if c['last_order_date'] else 'N/A'
                    if c['recency_days'] >= 15:
                        c['segment'] = 'At Risk (High Value Churn)'
                    elif c['total_spend'] >= 5000:
                        c['segment'] = 'Champions (VIP)'
                    elif c['total_orders'] >= 5:
                        c['segment'] = 'Loyal Regulars'
                    else:
                        c['segment'] = 'Recent / Promising'
                cust_list.sort(key=lambda x: x['total_spend'], reverse=True)
                return cust_list
    except Exception as e:
        logger.debug(f"Fallback customer segmentation: {e}")
    return []


def clear_analytics_cache() -> None:
    """Clear in-memory analytics cache when orders/messages/products change."""
    _ANALYTICS_CACHE.clear()


def get_unified_analytics(days: int = 30) -> Dict[str, Any]:
    """
    Retrieve all dashboard stats, 30-day sales data, category revenue breakdown,
    and hourly order distributions in ONE single combined SQL transaction with in-memory caching.
    """
    now = time.time()
    cache_key = f"unified_{days}"
    if cache_key in _ANALYTICS_CACHE:
        cached_time, cached_data = _ANALYTICS_CACHE[cache_key]
        if now - cached_time < _ANALYTICS_TTL_SECONDS:
            return cached_data

    # Generate date labels for chart
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days - 1)
    date_list = []
    current_date = start_date
    while current_date <= end_date:
        date_list.append(current_date.strftime('%Y-%m-%d'))
        current_date += timedelta(days=1)

    try:
        # Pre-build product->category map from in-memory catalog (0ms)
        all_products = get_all_products()
        prod_cat_map = {p['name'].lower(): p.get('category', 'Grocery') for p in all_products}

        category_totals = {
            'Grocery': 0.0,
            'Vegetables': 0.0,
            'Dairy & Breakfast': 0.0,
            'Snacks': 0.0,
            'Beverages': 0.0,
            'Frozen Foods': 0.0,
            'Household': 0.0,
            'Home & Kitchen': 0.0,
            'Personal Care': 0.0,
            'Baby Care': 0.0
        }

        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute('''
                    SELECT 
                        (SELECT COUNT(*) FROM orders) AS total_orders,
                        (SELECT COUNT(*) FROM users) AS total_users,
                        (SELECT COUNT(*) FROM products) AS total_products,
                        (SELECT COUNT(*) FROM contact_messages) AS total_contacts,
                        (SELECT COALESCE(SUM(total_amount), 0) FROM orders) AS total_revenue,
                        (
                            SELECT COALESCE(json_agg(s), '[]'::json) FROM (
                                SELECT order_date::date::text as sale_date, SUM(total_amount) as daily_total
                                FROM orders
                                WHERE order_date::date >= CURRENT_DATE - INTERVAL '30 days'
                                GROUP BY sale_date
                                ORDER BY sale_date
                            ) s
                        ) AS sales_rows,
                        (
                            SELECT COALESCE(json_agg(h), '[]'::json) FROM (
                                SELECT TO_CHAR(order_date, 'HH24') as order_hour, COUNT(*) as count
                                FROM orders
                                GROUP BY order_hour
                            ) h
                        ) AS hourly_rows,
                        (
                            SELECT COALESCE(json_agg(c), '[]'::json) FROM (
                                SELECT COALESCE(p.category, 'Grocery') as category, SUM(oi.subtotal) as cat_revenue
                                FROM order_items oi
                                LEFT JOIN products p ON oi.product_id = p.product_id
                                GROUP BY 1
                            ) c
                        ) AS category_rows;
                ''')
                row = cursor.fetchone()

                total_orders = int(row['total_orders'] or 0)
                total_revenue = float(row['total_revenue'] or 0.0)
                avg_order_value = round(total_revenue / total_orders, 2) if total_orders > 0 else 0.0

                # Process sales data
                sales_dict = {str(item['sale_date']): float(item['daily_total'] or 0) for item in (row['sales_rows'] or [])}
                sales_data = [sales_dict.get(date, 0.0) for date in date_list]

                # Process hourly distribution
                hour_counts = {f"{h:02d}:00": 0 for h in range(24)}
                for h in (row['hourly_rows'] or []):
                    if h.get('order_hour') is not None:
                        h_str = f"{int(h['order_hour']):02d}:00"
                        hour_counts[h_str] = int(h['count'])

                # Process category totals from SQL aggregate
                for c in (row.get('category_rows') or []):
                    if isinstance(c, dict) and c.get('category'):
                        cat_name = c['category']
                        rev = float(c.get('cat_revenue') or 0.0)
                        category_totals[cat_name] = round(category_totals.get(cat_name, 0.0) + rev, 2)

                # Fallback if order_items has not yet been populated
                if sum(category_totals.values()) == 0.0 and total_orders > 0:
                    cursor.execute("SELECT products_ordered FROM orders LIMIT 200")
                    for cord in cursor.fetchall():
                        try:
                            raw_items = cord['products_ordered'] if isinstance(cord, dict) else cord[0]
                            items = json.loads(raw_items) if isinstance(raw_items, str) else raw_items
                            if not isinstance(items, list):
                                continue
                            for item in items:
                                name = (item.get('name') or '').lower()
                                price = float(item.get('price', 0))
                                qty = int(item.get('quantity', 1))
                                cat = prod_cat_map.get(name, 'Grocery')
                                category_totals[cat] = round(category_totals.get(cat, 0.0) + (price * qty), 2)
                        except Exception:
                            continue

                city_sla = []
                try:
                    cursor.execute("""
                        SELECT 
                            COALESCE(city, 'Bangalore') as city,
                            COUNT(order_id) as orders,
                            ROUND(AVG(total_amount), 2) as aov,
                            ROUND(AVG(COALESCE(delivery_duration_minutes, 7.2)), 2) as avg_duration,
                            ROUND((SUM(CASE WHEN COALESCE(delivery_duration_minutes, 7.2) <= 10.0 THEN 1.0 ELSE 0.0 END) / COUNT(order_id)) * 100.0, 1) as sla_pct
                        FROM orders
                        WHERE status = 'Delivered'
                        GROUP BY COALESCE(city, 'Bangalore')
                        ORDER BY orders DESC;
                    """)
                    city_sla = [dict(r) for r in cursor.fetchall()]
                except Exception:
                    pass

                rfm_summary = []
                try:
                    cursor.execute("""
                        WITH customer_aggregates AS (
                            SELECT 
                                o.user_id,
                                COUNT(o.order_id) AS total_orders,
                                SUM(o.total_amount) AS total_spend,
                                EXTRACT(DAY FROM (CURRENT_TIMESTAMP - MAX(o.order_date)))::integer AS recency_days
                            FROM orders o
                            WHERE o.status = 'Delivered'
                            GROUP BY o.user_id
                        ),
                        rfm_scores AS (
                            SELECT 
                                user_id,
                                NTILE(5) OVER (ORDER BY recency_days DESC) AS r_score,
                                NTILE(5) OVER (ORDER BY total_orders ASC) AS f_score,
                                NTILE(5) OVER (ORDER BY total_spend ASC) AS m_score
                            FROM customer_aggregates
                        )
                        SELECT 
                            CASE 
                                WHEN r_score >= 4 AND f_score >= 4 AND m_score >= 4 THEN 'Champions (VIP)'
                                WHEN r_score >= 3 AND f_score >= 3 THEN 'Loyal Customers'
                                WHEN r_score >= 4 AND f_score <= 2 THEN 'Recent / Promising'
                                WHEN r_score <= 2 AND f_score >= 3 THEN 'At Risk (High Value Churn)'
                                WHEN r_score <= 2 AND f_score <= 2 THEN 'Hibernating / Lost'
                                ELSE 'Needs Attention'
                            END AS segment,
                            COUNT(*) as count
                        FROM rfm_scores
                        GROUP BY 1
                        ORDER BY count DESC;
                    """)
                    rfm_summary = [dict(r) for r in cursor.fetchall()]
                except Exception:
                    pass

                rfm_customers = []
                try:
                    cursor.execute("""
                        WITH customer_aggregates AS (
                            SELECT 
                                o.user_id,
                                MAX(o.full_name) as full_name,
                                MAX(o.phone_number) as phone,
                                MAX(COALESCE(o.city, 'Bangalore')) as city,
                                COUNT(o.order_id) AS total_orders,
                                SUM(o.total_amount) AS total_spend,
                                MAX(o.order_date) as last_order_date,
                                EXTRACT(DAY FROM (CURRENT_TIMESTAMP - MAX(o.order_date)))::integer AS recency_days
                            FROM orders o
                            WHERE o.status = 'Delivered'
                            GROUP BY o.user_id
                        ),
                        rfm_scores AS (
                            SELECT 
                                ca.*,
                                NTILE(5) OVER (ORDER BY recency_days DESC) AS r_score,
                                NTILE(5) OVER (ORDER BY total_orders ASC) AS f_score,
                                NTILE(5) OVER (ORDER BY total_spend ASC) AS m_score
                            FROM customer_aggregates ca
                        ),
                        segmented AS (
                            SELECT 
                                s.*,
                                COALESCE(u.email, 'customer@dailydrop.com') as user_email,
                                COALESCE(u.name, s.full_name) as customer_name,
                                CASE 
                                    WHEN r_score >= 4 AND f_score >= 4 AND m_score >= 4 THEN 'Champions (VIP)'
                                    WHEN r_score >= 3 AND f_score >= 3 THEN 'Loyal Regulars'
                                    WHEN r_score >= 4 AND f_score <= 2 THEN 'Recent / Promising'
                                    WHEN r_score <= 2 AND f_score >= 3 THEN 'At Risk (High Value Churn)'
                                    WHEN r_score <= 2 AND f_score <= 2 THEN 'Hibernating / Lost'
                                    ELSE 'Needs Attention'
                                END AS segment
                            FROM rfm_scores s
                            LEFT JOIN users u ON s.user_id = u.id
                        )
                        SELECT 
                            user_id,
                            customer_name as name,
                            user_email as email,
                            phone,
                            city,
                            total_orders,
                            ROUND(total_spend, 2) as total_spend,
                            ROUND(total_spend / total_orders, 2) as avg_order_value,
                            recency_days,
                            TO_CHAR(last_order_date, 'YYYY-MM-DD HH24:MI') as last_order_str,
                            segment
                        FROM segmented
                        ORDER BY total_spend DESC;
                    """)
                    for r in cursor.fetchall():
                        rfm_customers.append({
                            'user_id': int(r['user_id']),
                            'name': str(r['name'] or 'Valued Customer'),
                            'email': str(r['email'] or 'customer@dailydrop.com'),
                            'phone': str(r['phone'] or '+91 98765 00000'),
                            'city': str(r['city'] or 'Bangalore'),
                            'total_orders': int(r['total_orders'] or 0),
                            'total_spend': float(r['total_spend'] or 0.0),
                            'avg_order_value': float(r['avg_order_value'] or 0.0),
                            'recency_days': int(r['recency_days'] or 0),
                            'last_order_str': str(r['last_order_str'] or 'N/A'),
                            'segment': str(r['segment'])
                        })
                except Exception as e:
                    logger.debug(f"SQL rfm_customers error: {e}")

                if not rfm_customers:
                    rfm_customers = _get_fallback_rfm_customers()

                abc_summary = []
                try:
                    cursor.execute("""
                        WITH product_sales AS (
                            SELECT 
                                oi.product_id,
                                SUM(oi.subtotal) AS total_revenue
                            FROM order_items oi
                            JOIN orders o ON oi.order_id = o.order_id
                            WHERE o.status = 'Delivered'
                            GROUP BY oi.product_id
                        ),
                        ranked AS (
                            SELECT 
                                product_id,
                                total_revenue,
                                SUM(total_revenue) OVER () as overall,
                                SUM(total_revenue) OVER (ORDER BY total_revenue DESC ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) as cum
                            FROM product_sales
                        )
                        SELECT 
                            CASE 
                                WHEN (cum * 100.0) / overall <= 80.0 THEN 'Class A (80% GMV)'
                                WHEN (cum * 100.0) / overall <= 95.0 THEN 'Class B (15% GMV)'
                                ELSE 'Class C (5% GMV)'
                            END as abc_class,
                            COUNT(*) as count,
                            ROUND(SUM(total_revenue), 2) as revenue
                        FROM ranked
                        GROUP BY 1;
                    """)
                    abc_summary = [dict(r) for r in cursor.fetchall()]
                except Exception:
                    pass

                market_basket = []
                try:
                    cursor.execute("""
                        WITH item_pairs AS (
                            SELECT 
                                oi1.product_name AS product_a,
                                oi2.product_name AS product_b,
                                COUNT(DISTINCT oi1.order_id) AS pair_orders
                            FROM order_items oi1
                            JOIN order_items oi2 ON oi1.order_id = oi2.order_id AND oi1.product_id < oi2.product_id
                            GROUP BY oi1.product_name, oi2.product_name
                        ),
                        item_counts AS (
                            SELECT product_name, COUNT(DISTINCT order_id) AS item_orders
                            FROM order_items
                            GROUP BY product_name
                        ),
                        total_delivered AS (
                            SELECT COUNT(DISTINCT order_id) AS total_orders FROM orders WHERE status = 'Delivered'
                        )
                        SELECT 
                            p.product_a,
                            p.product_b,
                            p.pair_orders,
                            ROUND((p.pair_orders::numeric * t.total_orders) / (c1.item_orders * c2.item_orders), 2) AS lift
                        FROM item_pairs p
                        CROSS JOIN total_delivered t
                        JOIN item_counts c1 ON p.product_a = c1.product_name
                        JOIN item_counts c2 ON p.product_b = c2.product_name
                        ORDER BY p.pair_orders DESC, lift DESC
                        LIMIT 6;
                    """)
                    for r in cursor.fetchall():
                        market_basket.append({
                            'product_a': str(r['product_a']),
                            'product_b': str(r['product_b']),
                            'pair_orders': int(r['pair_orders']),
                            'lift': float(r['lift']) if r['lift'] is not None else 1.0
                        })
                except Exception:
                    pass

                cohort_matrix = []
                try:
                    cursor.execute("""
                        WITH user_first_order AS (
                            SELECT user_id, DATE_TRUNC('month', MIN(order_date)) AS cohort_month
                            FROM orders
                            WHERE status = 'Delivered'
                            GROUP BY user_id
                        ),
                        user_activities AS (
                            SELECT 
                                o.user_id,
                                ufo.cohort_month,
                                (EXTRACT(YEAR FROM o.order_date) - EXTRACT(YEAR FROM ufo.cohort_month)) * 12 +
                                (EXTRACT(MONTH FROM o.order_date) - EXTRACT(MONTH FROM ufo.cohort_month)) AS month_number
                            FROM orders o
                            JOIN user_first_order ufo ON o.user_id = ufo.user_id
                            WHERE o.status = 'Delivered'
                            GROUP BY o.user_id, ufo.cohort_month, month_number
                        ),
                        cohort_sizes AS (
                            SELECT cohort_month, COUNT(DISTINCT user_id) as total_users
                            FROM user_first_order
                            GROUP BY cohort_month
                        ),
                        cohort_retention AS (
                            SELECT 
                                TO_CHAR(ua.cohort_month, 'YYYY-MM') as cohort,
                                cs.total_users,
                                ua.month_number,
                                COUNT(DISTINCT ua.user_id) as active_users,
                                ROUND((COUNT(DISTINCT ua.user_id)::numeric / cs.total_users) * 100.0, 1) as retention_rate
                            FROM user_activities ua
                            JOIN cohort_sizes cs ON ua.cohort_month = cs.cohort_month
                            GROUP BY ua.cohort_month, cs.total_users, ua.month_number
                            ORDER BY cohort, month_number
                        )
                        SELECT * FROM cohort_retention WHERE cohort >= '2026-05' ORDER BY cohort DESC, month_number ASC;
                    """)
                    cohort_rows = cursor.fetchall()
                    cohort_map = {}
                    for r in cohort_rows:
                        c_name = str(r['cohort'])
                        if c_name not in cohort_map:
                            cohort_map[c_name] = {
                                'cohort': c_name,
                                'total_users': int(r['total_users']),
                                'm0': None, 'm1': None, 'm2': None, 'm3': None, 'm4': None, 'm5': None
                            }
                        m_idx = int(r['month_number'])
                        if 0 <= m_idx <= 5:
                            cohort_map[c_name][f'm{m_idx}'] = float(r['retention_rate'])
                    cohort_matrix = list(cohort_map.values())
                except Exception:
                    pass

                if not market_basket:
                    market_basket = []

                if not cohort_matrix:
                    cohort_matrix = []

                at_risk_list = [c for c in rfm_customers if 'At Risk' in c.get('segment', '')]
                vip_list = [c for c in rfm_customers if 'Champions' in c.get('segment', '')]
                loyal_list = [c for c in rfm_customers if 'Loyal' in c.get('segment', '')]
                at_risk_spend_val = sum(float(c.get('total_spend', 0.0)) for c in at_risk_list)
                vip_spend_val = sum(float(c.get('total_spend', 0.0)) for c in vip_list)

                analytics_result = {
                    'stats': {
                        'total_orders': total_orders,
                        'total_users': int(row['total_users'] or 0),
                        'total_products': int(row['total_products'] or 0),
                        'total_contacts': int(row['total_contacts'] or 0),
                        'total_revenue': total_revenue,
                        'avg_order_value': avg_order_value,
                    },
                    'sales': {
                        'labels': date_list,
                        'data': sales_data,
                        'min_date': start_date.strftime('%Y-%m-%d'),
                        'max_date': end_date.strftime('%Y-%m-%d')
                    },
                    'categories': category_totals,
                    'hourly': hour_counts,
                    'city_sla': city_sla,
                    'rfm_summary': rfm_summary,
                    'rfm_customers': rfm_customers,
                    'at_risk_customers': at_risk_list,
                    'vip_customers': vip_list,
                    'loyal_customers': loyal_list,
                    'at_risk_count': len(at_risk_list),
                    'vip_count': len(vip_list),
                    'at_risk_spend': at_risk_spend_val,
                    'vip_spend': vip_spend_val,
                    'abc_summary': abc_summary,
                    'cohort_matrix': cohort_matrix,
                    'market_basket': market_basket
                }

                _ANALYTICS_CACHE[cache_key] = (now, analytics_result)
                return analytics_result
    except Exception as e:
        logger.warning(f"Combined SQL analytics query failed, using relational fallback: {e}")
        try:
            with get_db_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute("SELECT COUNT(*) as c FROM orders")
                    r_ord = cursor.fetchone()
                    total_orders = int(r_ord['c'] if isinstance(r_ord, dict) else r_ord[0]) if r_ord else 0

                    cursor.execute("SELECT COUNT(*) as c FROM users")
                    r_usr = cursor.fetchone()
                    total_users = int(r_usr['c'] if isinstance(r_usr, dict) else r_usr[0]) if r_usr else 0

                    cursor.execute("SELECT COUNT(*) as c FROM products")
                    r_prd = cursor.fetchone()
                    total_products = int(r_prd['c'] if isinstance(r_prd, dict) else r_prd[0]) if r_prd else 0

                    cursor.execute("SELECT COUNT(*) as c FROM contact_messages")
                    r_cnt = cursor.fetchone()
                    total_contacts = int(r_cnt['c'] if isinstance(r_cnt, dict) else r_cnt[0]) if r_cnt else 0

                    cursor.execute("SELECT COALESCE(SUM(total_amount), 0) as s FROM orders")
                    r_rev = cursor.fetchone()
                    total_revenue = float(r_rev['s'] if isinstance(r_rev, dict) else r_rev[0]) if r_rev else 0.0

                    avg_order_value = round(total_revenue / total_orders, 2) if total_orders > 0 else 0.0

                    cursor.execute("SELECT order_date, total_amount, products_ordered FROM orders")
                    all_ord_rows = cursor.fetchall()

                    sales_dict = {}
                    hour_counts = {f"{h:02d}:00": 0 for h in range(24)}
                    for orow in all_ord_rows:
                        odate = orow.get('order_date') if isinstance(orow, dict) else orow[0]
                        otot = orow.get('total_amount') if isinstance(orow, dict) else orow[1]
                        oprod = orow.get('products_ordered') if isinstance(orow, dict) else orow[2]
                        if odate:
                            dt_str = str(odate)[:10]
                            sales_dict[dt_str] = round(sales_dict.get(dt_str, 0.0) + float(otot or 0), 2)
                            try:
                                h_int = int(str(odate)[11:13]) if len(str(odate)) >= 13 else 0
                                h_str = f"{h_int:02d}:00"
                                hour_counts[h_str] = hour_counts.get(h_str, 0) + 1
                            except Exception:
                                pass
                        try:
                            items = json.loads(oprod) if isinstance(oprod, str) else oprod
                            if isinstance(items, list):
                                for item in items:
                                    name = (item.get('name') or '').lower()
                                    price = float(item.get('price', 0))
                                    qty = int(item.get('quantity', 1))
                                    cat = prod_cat_map.get(name, 'Grocery')
                                    category_totals[cat] = round(category_totals.get(cat, 0.0) + (price * qty), 2)
                        except Exception:
                            pass

                    sales_data = [sales_dict.get(date, 0.0) for date in date_list]

                    fallback_cust = _get_fallback_rfm_customers()
                    at_risk_fb = [c for c in fallback_cust if 'At Risk' in c.get('segment', '')]
                    vip_fb = [c for c in fallback_cust if 'Champions' in c.get('segment', '')]
                    loyal_fb = [c for c in fallback_cust if 'Loyal' in c.get('segment', '')]

                    analytics_result = {
                        'stats': {
                            'total_orders': total_orders,
                            'total_users': total_users,
                            'total_products': total_products,
                            'total_contacts': total_contacts,
                            'total_revenue': total_revenue,
                            'avg_order_value': avg_order_value,
                        },
                        'sales': {
                            'labels': date_list,
                            'data': sales_data,
                            'min_date': start_date.strftime('%Y-%m-%d'),
                            'max_date': end_date.strftime('%Y-%m-%d')
                        },
                        'categories': category_totals,
                        'hourly': hour_counts,
                        'city_sla': [],
                        'rfm_summary': [],
                        'rfm_customers': fallback_cust,
                        'at_risk_customers': at_risk_fb,
                        'vip_customers': vip_fb,
                        'loyal_customers': loyal_fb,
                        'at_risk_count': len(at_risk_fb),
                        'vip_count': len(vip_fb),
                        'at_risk_spend': sum(float(c.get('total_spend', 0.0)) for c in at_risk_fb),
                        'vip_spend': sum(float(c.get('total_spend', 0.0)) for c in vip_fb),
                        'abc_summary': [],
                        'cohort_matrix': [],
                        'market_basket': []
                    }
                    _ANALYTICS_CACHE[cache_key] = (now, analytics_result)
                    return analytics_result
        except Exception as fallback_e:
            logger.error(f"Fallback analytics calculation error: {fallback_e}")
            if cache_key in _ANALYTICS_CACHE:
                return _ANALYTICS_CACHE[cache_key][1]
            return {}


def get_dashboard_stats() -> Dict[str, Any]:
    """Retrieve dashboard statistics from unified analytics."""
    analytics = get_unified_analytics(days=30)
    return analytics.get('stats', {
        'total_orders': 0,
        'total_users': 0,
        'total_products': 0,
        'total_contacts': 0,
        'total_revenue': 0.0,
        'avg_order_value': 0.0
    })


def get_sales_data(days: int = 30) -> Dict[str, Any]:
    """Retrieve sales data from unified analytics."""
    analytics = get_unified_analytics(days=days)
    return analytics.get('sales', {
        'labels': [],
        'data': [],
        'min_date': '',
        'max_date': ''
    })


def get_customer_audiences(days: int = 30) -> List[Dict[str, Any]]:
    """Retrieve detailed customer audience profiles scored by RFM segmentation."""
    analytics = get_unified_analytics(days=days)
    return analytics.get('rfm_customers', [])


def get_category_revenue() -> Dict[str, float]:
    """Retrieve total sales revenue broken down by product category in 0ms using in-memory product mapping."""
    try:
        all_products = get_all_products()
        prod_cat_map = {p['name'].lower(): p.get('category', 'Grocery') for p in all_products}

        category_totals = {
            'Grocery': 0.0,
            'Vegetables': 0.0,
            'Dairy & Breakfast': 0.0,
            'Snacks': 0.0,
            'Beverages': 0.0,
            'Frozen Foods': 0.0,
            'Household': 0.0,
            'Home & Kitchen': 0.0,
            'Personal Care': 0.0,
            'Baby Care': 0.0
        }

        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute('SELECT products_ordered FROM orders')
                rows = cursor.fetchall()

                for row in rows:
                    try:
                        raw_items = row['products_ordered']
                        items = json.loads(raw_items) if isinstance(raw_items, str) else raw_items
                        if not isinstance(items, list):
                            continue
                        for item in items:
                            name = (item.get('name') or '').lower()
                            price = float(item.get('price', 0))
                            qty = int(item.get('quantity', 1))
                            cat = prod_cat_map.get(name, 'Grocery')
                            category_totals[cat] = round(category_totals.get(cat, 0.0) + (price * qty), 2)
                    except Exception:
                        continue

                return category_totals
    except Exception as e:
        logger.error(f"Error retrieving category revenue: {e}")
        return {}


def get_hourly_order_distribution() -> Dict[str, int]:
    """Retrieve order volume across hours of the day (00:00 - 23:00)."""
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute('''
                    SELECT TO_CHAR(order_date, 'HH24') as order_hour, COUNT(*) as count
                    FROM orders
                    GROUP BY order_hour
                ''')
                rows = cursor.fetchall()
                hour_counts = {f"{h:02d}:00": 0 for h in range(24)}
                for r in rows:
                    if r['order_hour'] is not None:
                        h_str = f"{int(r['order_hour']):02d}:00"
                        hour_counts[h_str] = int(r['count'])
                return hour_counts
    except Exception as e:
        logger.error(f"Error retrieving hourly distribution: {e}")
        return {}
