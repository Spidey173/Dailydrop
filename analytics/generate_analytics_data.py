"""
DailyDrop E-Commerce Data Analytics Pipeline - Realistic Dataset Generator
Generates portfolio-grade, high-volume transactional data spanning 12 months with
realistic consumer cohorts, market basket product affinities, peak hour distributions,
and 10-minute quick-commerce delivery SLA tracking.
"""

import os
import json
import random
import math
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

# Set deterministic seed for reproducible results
RANDOM_SEED = 42
random.seed(RANDOM_SEED)
np.random.seed(RANDOM_SEED)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
DATA_DIR = os.path.join(BASE_DIR, 'data')
os.makedirs(DATA_DIR, exist_ok=True)

# -----------------------------------------------------------------------------
# 1. Load Products Catalog from Official Catalog
# -----------------------------------------------------------------------------
def load_catalog():
    js_path = os.path.join(PROJECT_ROOT, 'static', 'js', 'products.js')
    if os.path.exists(js_path):
        with open(js_path, 'r', encoding='utf-8') as f:
            text = f.read()
        start = text.find('[')
        end = text.rfind(']') + 1
        raw_products = json.loads(text[start:end])
    else:
        # Fallback minimal catalog
        raw_products = [
            {"id": 1, "title": "Amul Taaza Milk 1L", "category": "Dairy & Breakfast", "subcategory": "Milk", "price": 72.0},
            {"id": 2, "title": "Harvest Gold Brown Bread", "category": "Dairy & Breakfast", "subcategory": "Bread", "price": 45.0},
            {"id": 3, "title": "Farm Fresh Robusta Bananas 1kg", "category": "Fruits & Vegetables", "subcategory": "Fruits", "price": 45.0},
            {"id": 4, "title": "Aashirvaad Superior MP Sharbati Atta 5kg", "category": "Grocery", "subcategory": "Atta", "price": 310.0},
            {"id": 5, "title": "Brooke Bond Red Label Tea 500g", "category": "Beverages", "subcategory": "Tea", "price": 260.0},
        ]

    products = []
    # Assign wholesale cost price estimating realistic grocery gross margins:
    # Fresh Produce: ~30-35% margin | Staples/Grocery: ~15-20% margin | Snacks/Personal: ~25-30% margin
    margin_by_category = {
        'Fruits & Vegetables': 0.32,
        'Dairy & Breakfast': 0.18,
        'Grocery': 0.16,
        'Snacks': 0.28,
        'Beverages': 0.25,
        'Personal Care': 0.35,
        'Household': 0.30,
        'Baby Care': 0.20,
        'Home & Kitchen': 0.38,
        'Frozen Foods': 0.26
    }

    for p in raw_products:
        cat = p.get('category', 'Grocery')
        selling_price = float(p.get('price', 50.0))
        margin = margin_by_category.get(cat, 0.22)
        # Cost price = selling price * (1 - margin)
        cost_price = round(selling_price * (1.0 - margin), 2)

        products.append({
            'product_id': p['id'],
            'name': p['title'],
            'category': cat,
            'subcategory': p.get('subcategory', 'General'),
            'selling_price': selling_price,
            'cost_price': cost_price,
            'margin_pct': round(margin * 100, 1),
            'stock': random.randint(25, 150)
        })

    return pd.DataFrame(products)


# -----------------------------------------------------------------------------
# 2. Generate Customer Personas & Cohorts
# -----------------------------------------------------------------------------
FIRST_NAMES = [
    'Aarav', 'Vivaan', 'Aditya', 'Vihaan', 'Arjun', 'Sai', 'Reyansh', 'Ayaan', 'Krishna', 'Ishaan',
    'Shaurya', 'Ananya', 'Diya', 'Aadhya', 'Pari', 'Saanvi', 'Anushka', 'Khushi', 'Aditi', 'Prisha',
    'Rohan', 'Sneha', 'Rahul', 'Pooja', 'Vikram', 'Neha', 'Karan', 'Priya', 'Amit', 'Sunita',
    'Deepak', 'Meera', 'Rajesh', 'Kavita', 'Suresh', 'Anita', 'Manish', 'Shweta', 'Naveen', 'Ritu'
]
LAST_NAMES = [
    'Sharma', 'Verma', 'Patel', 'Reddy', 'Nair', 'Iyer', 'Gupta', 'Singh', 'Kumar', 'Mehta',
    'Chopra', 'Joshi', 'Bhat', 'Rao', 'Kulkarni', 'Deshmukh', 'Menon', 'Pillai', 'Agarwal', 'Banerjee'
]
CITIES = [
    ('Bangalore', '560001', 'Karnataka'),
    ('Bangalore', '560034', 'Karnataka'),
    ('Bangalore', '560102', 'Karnataka'),
    ('Mumbai', '400001', 'Maharashtra'),
    ('Mumbai', '400050', 'Maharashtra'),
    ('Delhi NCR', '110001', 'Delhi'),
    ('Delhi NCR', '122001', 'Haryana'),
    ('Hyderabad', '500081', 'Telangana'),
    ('Pune', '411001', 'Maharashtra')
]

def generate_customers(num_customers=250, start_date=datetime(2025, 11, 1), end_date=datetime(2026, 10, 31)):
    customers = []
    total_days = (end_date - start_date).days

    # Customer Archetypes:
    # 1. Daily Essentials (high frequency, low AOV)
    # 2. Family Pantry (moderate frequency, high AOV)
    # 3. Impulse & Snacks (moderate frequency, evening buyer)
    # 4. Churned / Inactive (1-2 early orders, then zero)
    archetypes = ['Daily Essentials', 'Family Pantry', 'Impulse & Snacks', 'Occasional']
    archetype_weights = [0.35, 0.25, 0.20, 0.20]

    for cid in range(1, num_customers + 1):
        fname = random.choice(FIRST_NAMES)
        lname = random.choice(LAST_NAMES)
        full_name = f"{fname} {lname}"
        email = f"{fname.lower()}.{lname.lower()}{random.randint(10, 999)}@gmail.com"
        phone = f"{random.choice(['98', '97', '99', '91', '88', '70'])}{random.randint(10000000, 99999999)}"
        city_info = random.choice(CITIES)
        address = f"Flat #{random.randint(101, 1404)}, Tower {random.choice(['A', 'B', 'C', 'D'])}, {city_info[0]} - {city_info[1]}"
        
        # User acquisition staggered over the year with growth curve
        day_offset = int((random.random() ** 0.7) * total_days)
        signup_dt = start_date + timedelta(days=day_offset)
        persona = random.choices(archetypes, weights=archetype_weights)[0]

        customers.append({
            'customer_id': cid,
            'name': full_name,
            'email': email,
            'phone': phone,
            'city': city_info[0],
            'postal_code': city_info[1],
            'state': city_info[2],
            'address': address,
            'signup_date': signup_dt.strftime('%Y-%m-%d %H:%M:%S'),
            'signup_month': signup_dt.strftime('%Y-%m'),
            'persona': persona
        })

    return pd.DataFrame(customers)


# -----------------------------------------------------------------------------
# 3. Generate Realistic Orders with Market Basket Affinities & SLAs
# -----------------------------------------------------------------------------
def generate_orders_and_items(products_df, customers_df, num_orders=2500, start_date=datetime(2025, 11, 1), end_date=datetime(2026, 10, 31)):
    # Group products by category for affinity sampling
    cat_products = {}
    for cat, group in products_df.groupby('category'):
        cat_products[cat] = group.to_dict('records')

    all_products_list = products_df.to_dict('records')

    # Common Market Basket Pairings:
    # If Dairy -> high chance of Bread, Eggs, Fruit
    # If Grocery (Rice/Atta) -> Dal, Oil, Salt
    # If Snacks -> Beverage, Confectionery
    orders = []
    order_items = []
    item_counter = 1

    total_days = (end_date - start_date).days
    customers_list = customers_df.to_dict('records')

    # Assign target order count based on persona
    order_id = 1
    for cust in customers_list:
        c_signup = datetime.strptime(cust['signup_date'], '%Y-%m-%d %H:%M:%S')
        days_active = max(1, (end_date - c_signup).days)
        months_active = max(1, days_active / 30.0)

        persona = cust['persona']
        if persona == 'Daily Essentials':
            # 3 to 7 orders per month
            target_orders = int(months_active * random.uniform(3.0, 7.0))
        elif persona == 'Family Pantry':
            # 1 to 3 large orders per month
            target_orders = int(months_active * random.uniform(1.2, 2.5))
        elif persona == 'Impulse & Snacks':
            # 2 to 5 orders per month
            target_orders = int(months_active * random.uniform(2.0, 4.5))
        else: # Occasional / At Risk
            target_orders = random.choices([1, 2, 3], weights=[0.6, 0.3, 0.1])[0]

        target_orders = max(1, target_orders)

        # Distribute orders between signup_date and end_date
        cust_order_dates = []
        for _ in range(target_orders):
            if persona == 'Occasional':
                # Early churn: cluster near signup date
                day_delta = random.randint(0, min(45, days_active))
            else:
                day_delta = random.randint(0, days_active)
            cust_order_dates.append(c_signup + timedelta(days=day_delta))

        cust_order_dates.sort()

        for o_date in cust_order_dates:
            # Determine peak hour distributions
            # Morning Rush: 7 - 10 AM (Breakfast / Milk / Fresh veggies)
            # Evening Rush: 5 - 10 PM (Dinner prep, snacks, night cravings)
            hour_roll = random.random()
            if persona == 'Daily Essentials' or hour_roll < 0.35:
                # Morning peak
                hour = random.choice([7, 8, 9, 10])
                minute = random.randint(0, 59)
                primary_cat = random.choice(['Dairy & Breakfast', 'Fruits & Vegetables'])
            elif persona == 'Impulse & Snacks' or hour_roll < 0.75:
                # Evening peak
                hour = random.choice([17, 18, 19, 20, 21])
                minute = random.randint(0, 59)
                primary_cat = random.choice(['Snacks', 'Beverages', 'Dairy & Breakfast'])
            else:
                # Afternoon or lunch
                hour = random.choice([11, 12, 13, 14, 15, 16])
                minute = random.randint(0, 59)
                primary_cat = random.choice(list(cat_products.keys()))

            order_timestamp = o_date.replace(hour=hour, minute=minute, second=random.randint(0, 59))

            # Assemble realistic cart items based on persona & primary category
            cart_items = []
            selected_product_ids = set()

            if persona == 'Family Pantry':
                basket_size = random.randint(4, 9)
            elif persona == 'Daily Essentials':
                basket_size = random.randint(2, 5)
            else:
                basket_size = random.randint(1, 4)

            # Pick 1-2 items from primary category
            primary_candidates = cat_products.get(primary_cat, all_products_list)
            num_primary = min(len(primary_candidates), random.randint(1, 2))
            for p in random.sample(primary_candidates, num_primary):
                if p['product_id'] not in selected_product_ids:
                    selected_product_ids.add(p['product_id'])
                    cart_items.append(p)

            # Cross-sell logic: Add correlated companion products
            if primary_cat == 'Dairy & Breakfast':
                # Add Bakery or Fruits
                companion_pool = cat_products.get('Fruits & Vegetables', []) + cat_products.get('Snacks', [])
            elif primary_cat == 'Grocery':
                # Add Oil, Salt, or Veggies
                companion_pool = cat_products.get('Fruits & Vegetables', []) + cat_products.get('Dairy & Breakfast', [])
            elif primary_cat == 'Snacks':
                companion_pool = cat_products.get('Beverages', [])
            else:
                companion_pool = all_products_list

            while len(cart_items) < basket_size and companion_pool:
                candidate = random.choice(companion_pool)
                if candidate['product_id'] not in selected_product_ids:
                    selected_product_ids.add(candidate['product_id'])
                    cart_items.append(candidate)
                else:
                    break

            if not cart_items:
                cart_items = [random.choice(all_products_list)]

            # Compute Order Financials
            order_subtotal = 0.0
            order_cost_total = 0.0
            order_item_records = []

            for p in cart_items:
                qty = random.choices([1, 2, 3, 4], weights=[0.70, 0.20, 0.07, 0.03])[0]
                line_subtotal = round(p['selling_price'] * qty, 2)
                line_cost = round(p['cost_price'] * qty, 2)
                gross_profit = round(line_subtotal - line_cost, 2)

                order_subtotal += line_subtotal
                order_cost_total += line_cost

                order_item_records.append({
                    'item_id': item_counter,
                    'order_id': order_id,
                    'product_id': p['product_id'],
                    'product_name': p['name'],
                    'category': p['category'],
                    'subcategory': p['subcategory'],
                    'unit_price': p['selling_price'],
                    'unit_cost': p['cost_price'],
                    'quantity': qty,
                    'line_subtotal': line_subtotal,
                    'line_cost': line_cost,
                    'gross_profit': gross_profit,
                    'order_date': order_timestamp.strftime('%Y-%m-%d %H:%M:%S')
                })
                item_counter += 1

            # Delivery Fee: Free delivery over Rs. 500
            order_subtotal = round(order_subtotal, 2)
            delivery_fee = 0.0 if order_subtotal >= 500.0 else 30.0
            final_total = round(order_subtotal + delivery_fee, 2)
            gross_margin_pct = round(((order_subtotal - order_cost_total) / max(0.01, order_subtotal)) * 100, 1)

            # Payment method: 62% Razorpay/Online (UPI/Cards), 38% Cash on Delivery (COD)
            payment_method = random.choices(['Razorpay', 'COD'], weights=[0.62, 0.38])[0]
            payment_id = f"pay_live_{random.randint(100000, 999999)}" if payment_method == 'Razorpay' else None

            # 10-Minute SLA Dispatch Simulation
            # Log-normal distribution of quick-commerce delivery minutes (mean ~ 7.4 mins)
            delivery_duration = round(np.random.normal(loc=7.2, scale=1.4), 1)
            delivery_duration = max(3.5, delivery_duration)
            sla_breached = delivery_duration > 10.0 # SLA is 10 minutes

            status = random.choices(['Delivered', 'Cancelled'], weights=[0.97, 0.03])[0]

            orders.append({
                'order_id': order_id,
                'customer_id': cust['customer_id'],
                'customer_name': cust['name'],
                'customer_email': cust['email'],
                'city': cust['city'],
                'order_date': order_timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                'order_year_month': order_timestamp.strftime('%Y-%m'),
                'day_of_week': order_timestamp.strftime('%A'),
                'hour_of_day': order_timestamp.hour,
                'items_count': len(cart_items),
                'total_quantity': sum(i['quantity'] for i in order_item_records),
                'subtotal': order_subtotal,
                'delivery_fee': delivery_fee,
                'total_amount': final_total,
                'total_cost': round(order_cost_total, 2),
                'gross_profit': round(order_subtotal - order_cost_total, 2),
                'gross_margin_pct': gross_margin_pct,
                'payment_method': payment_method,
                'payment_id': payment_id,
                'status': status,
                'delivery_duration_minutes': delivery_duration,
                'sla_breached': sla_breached
            })

            order_items.extend(order_item_records)
            order_id += 1

    return pd.DataFrame(orders), pd.DataFrame(order_items)


# -----------------------------------------------------------------------------
# 4. Generate Precomputed RFM Segmentation
# -----------------------------------------------------------------------------
def calculate_rfm(orders_df, customers_df, reference_date=datetime(2026, 11, 1)):
    # Filter completed orders
    valid_orders = orders_df[orders_df['status'] == 'Delivered'].copy()
    valid_orders['order_date_dt'] = pd.to_datetime(valid_orders['order_date'])

    # Aggregate by customer
    rfm = valid_orders.groupby('customer_id').agg(
        last_order_date=('order_date_dt', 'max'),
        total_orders=('order_id', 'count'),
        total_spend=('total_amount', 'sum'),
        avg_order_value=('total_amount', 'mean')
    ).reset_index()

    rfm['recency_days'] = (reference_date - rfm['last_order_date']).dt.days

    # Merge customer info
    rfm = pd.merge(customers_df[['customer_id', 'name', 'email', 'city', 'signup_date', 'persona']], rfm, on='customer_id', how='left')
    rfm['total_orders'] = rfm['total_orders'].fillna(0).astype(int)
    rfm['total_spend'] = rfm['total_spend'].fillna(0.0).round(2)
    rfm['avg_order_value'] = rfm['avg_order_value'].fillna(0.0).round(2)
    rfm['recency_days'] = rfm['recency_days'].fillna(365).astype(int)

    # Quintile Scoring (1 to 5)
    # Recency: Lower is better (5 is most recent)
    # Frequency & Monetary: Higher is better (5 is highest)
    rfm['r_score'] = pd.qcut(rfm['recency_days'], q=5, labels=[5, 4, 3, 2, 1], duplicates='drop').astype(int)
    rfm['f_score'] = pd.qcut(rfm['total_orders'].rank(method='first'), q=5, labels=[1, 2, 3, 4, 5]).astype(int)
    rfm['m_score'] = pd.qcut(rfm['total_spend'].rank(method='first'), q=5, labels=[1, 2, 3, 4, 5]).astype(int)

    rfm['rfm_combined'] = rfm['r_score'].astype(str) + rfm['f_score'].astype(str) + rfm['m_score'].astype(str)
    rfm['rfm_score'] = (rfm['r_score'] + rfm['f_score'] + rfm['m_score']) / 3.0
    rfm['rfm_score'] = rfm['rfm_score'].round(2)

    # Standard E-Commerce RFM Segmentation Rules
    def segment_customer(row):
        r, f, m = row['r_score'], row['f_score'], row['m_score']
        if r >= 4 and f >= 4 and m >= 4:
            return 'Champions (VIP)'
        elif r >= 3 and f >= 3:
            return 'Loyal Customers'
        elif r >= 4 and f <= 2:
            return 'Recent / Promising New'
        elif r == 3 and f <= 2:
            return 'Needs Attention'
        elif r <= 2 and f >= 3:
            return 'At Risk (High Value Inactive)'
        elif r <= 2 and f <= 2 and m >= 3:
            return 'About to Sleep'
        else:
            return 'Hibernating / Lost'

    rfm['customer_segment'] = rfm.apply(segment_customer, axis=1)
    return rfm


# -----------------------------------------------------------------------------
# Main Generation Runner
# -----------------------------------------------------------------------------
def run():
    print("=" * 70)
    print("🛒 DailyDrop Advanced Analytics Dataset Generator")
    print("=" * 70)

    # 1. Products
    print("📦 Loading authoritative product catalog...")
    products_df = load_catalog()
    products_path = os.path.join(DATA_DIR, 'products.csv')
    products_df.to_csv(products_path, index=False)
    print(f"   -> Saved {len(products_df)} products to {products_path}")

    # 2. Customers
    print("👥 Generating customer demographics & cohort personas...")
    customers_df = generate_customers(num_customers=250)
    customers_path = os.path.join(DATA_DIR, 'customers.csv')
    customers_df.to_csv(customers_path, index=False)
    print(f"   -> Saved {len(customers_df)} customers to {customers_path}")

    # 3. Orders & Order Items
    print("🚚 Simulating 12 months of Quick-Commerce orders and delivery SLAs...")
    orders_df, order_items_df = generate_orders_and_items(products_df, customers_df)
    orders_path = os.path.join(DATA_DIR, 'orders.csv')
    order_items_path = os.path.join(DATA_DIR, 'order_items.csv')
    orders_df.to_csv(orders_path, index=False)
    order_items_df.to_csv(order_items_path, index=False)
    print(f"   -> Saved {len(orders_df)} orders to {orders_path}")
    print(f"   -> Saved {len(order_items_df)} order items to {order_items_path}")

    # 4. RFM Segmentation
    print("🎯 Computing RFM Customer Segmentation...")
    rfm_df = calculate_rfm(orders_df, customers_df)
    rfm_path = os.path.join(DATA_DIR, 'customer_rfm.csv')
    rfm_df.to_csv(rfm_path, index=False)
    print(f"   -> Saved {len(rfm_df)} segmented customers to {rfm_path}")

    print("\n📊 Summary Statistics:")
    total_gmv = orders_df[orders_df['status'] == 'Delivered']['total_amount'].sum()
    total_profit = orders_df[orders_df['status'] == 'Delivered']['gross_profit'].sum()
    aov = orders_df[orders_df['status'] == 'Delivered']['total_amount'].mean()
    sla_compliance = (1 - orders_df['sla_breached'].mean()) * 100

    print(f"   • Total GMV (Delivered)    : Rs. {total_gmv:,.2f}")
    print(f"   • Total Gross Profit       : Rs. {total_profit:,.2f} (Margin: {(total_profit/total_gmv)*100:.1f}%)")
    print(f"   • Total Order Count        : {len(orders_df):,} orders")
    print(f"   • Average Order Value (AOV): Rs. {aov:.2f}")
    print(f"   • 10-Min SLA On-Time Rate  : {sla_compliance:.1f}%")
    print("=" * 70)
    print("✅ All datasets generated successfully in analytics/data/!")

if __name__ == '__main__':
    run()

