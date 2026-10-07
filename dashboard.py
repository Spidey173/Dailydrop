from flask import Flask, render_template_string, request, redirect, url_for, flash, session, jsonify
import os
import json
from datetime import datetime, timedelta
from psycopg2.extras import RealDictCursor

from config import Config
from database import get_db_connection, init_database

app = Flask(__name__)
app.secret_key = Config.SECRET_KEY

# Initialize database when app starts
with app.app_context():
    try:
        init_database()
    except Exception as e:
        print(f"Database init in dashboard: {e}")


# Helper functions for dashboard
def get_stats():
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as c:
            c.execute('SELECT COUNT(*) as count FROM orders')
            total_orders = c.fetchone()['count'] or 0

            c.execute('SELECT COUNT(*) as count FROM users')
            total_users = c.fetchone()['count'] or 0

            c.execute('SELECT COUNT(*) as count FROM products')
            total_products = c.fetchone()['count'] or 0

            c.execute('SELECT COUNT(*) as count FROM contact_messages')
            total_contacts = c.fetchone()['count'] or 0

            c.execute('SELECT SUM(total_amount) as total FROM orders')
            total_revenue_result = c.fetchone()['total']
            total_revenue = float(total_revenue_result) if total_revenue_result is not None else 0.0
            avg_order_value = round(total_revenue / total_orders, 2) if total_orders > 0 else 0.0

    return {
        'total_orders': total_orders,
        'total_users': total_users,
        'total_products': total_products,
        'total_revenue': total_revenue,
        'avg_order_value': avg_order_value,
        'total_contacts': total_contacts
    }


def get_category_stats():
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as c:
            c.execute('''
                SELECT category, COUNT(*) as count
                FROM products 
                GROUP BY category
            ''')
            categories = [dict(row) for row in c.fetchall()]
    return categories


def get_recent_orders(limit=5):
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as c:
            c.execute('''
                SELECT orders.*, users.name as user_name 
                FROM orders 
                JOIN users ON orders.user_id = users.id 
                ORDER BY order_date DESC 
                LIMIT %s
            ''', (limit,))
            orders = c.fetchall()

    parsed_orders = []
    for order in orders:
        order_dict = dict(order)
        try:
            order_dict['products'] = json.loads(order_dict['products_ordered'])
        except Exception:
            order_dict['products'] = []
        parsed_orders.append(order_dict)

    return parsed_orders


def get_recent_contacts(limit=5):
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as c:
            c.execute('''
                SELECT id, name, email, phone, subject, message, timestamp
                FROM contact_messages 
                ORDER BY timestamp DESC 
                LIMIT %s
            ''', (limit,))
            contacts = c.fetchall()

    return [dict(contact) for contact in contacts]


def get_top_products(limit=5):
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as c:
            c.execute('SELECT products_ordered FROM orders')
            all_orders = c.fetchall()

            product_counts = {}
            for order in all_orders:
                try:
                    products = json.loads(order['products_ordered'])
                    for product in products:
                        name = product['name']
                        quantity = product.get('quantity', 1)
                        product_counts[name] = product_counts.get(name, 0) + quantity
                except Exception:
                    continue

            sorted_products = sorted(product_counts.items(), key=lambda x: x[1], reverse=True)[:limit]

            top_products = []
            for name, count in sorted_products:
                c.execute('SELECT * FROM products WHERE name = %s', (name,))
                product = c.fetchone()
                if product:
                    top_products.append({
                        'name': name,
                        'count': count,
                        'price': float(product['price']),
                        'image_path': product['image_path']
                    })

    return top_products


def get_user_activity():
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as c:
            c.execute('''
                SELECT users.id, users.name, users.email, COUNT(orders.order_id) as order_count
                FROM users
                LEFT JOIN orders ON users.id = orders.user_id
                GROUP BY users.id, users.name, users.email
                ORDER BY order_count DESC
                LIMIT 5
            ''')
            active_users = [dict(r) for r in c.fetchall()]

            c.execute('''
                SELECT name, email, id 
                FROM users 
                ORDER BY id DESC 
                LIMIT 5
            ''')
            recent_users = [dict(r) for r in c.fetchall()]

    return {
        'active_users': active_users,
        'recent_users': recent_users
    }


def get_sales_data(days=30):
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as c:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days - 1)

            date_list = []
            current_date = start_date
            while current_date <= end_date:
                date_list.append(current_date.strftime('%Y-%m-%d'))
                current_date += timedelta(days=1)

            c.execute('''
                SELECT order_date::date as sale_date, 
                       SUM(total_amount) as daily_total
                FROM orders
                WHERE order_date::date BETWEEN %s AND %s
                GROUP BY sale_date
                ORDER BY sale_date
            ''', (start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')))

            daily_sales = c.fetchall()

    sales_dict = {str(row['sale_date']): float(row['daily_total'] or 0) for row in daily_sales}
    sales_data = [sales_dict.get(date, 0.0) for date in date_list]

    return {
        'labels': date_list,
        'data': sales_data,
        'min_date': start_date.strftime('%Y-%m-%d'),
        'max_date': end_date.strftime('%Y-%m-%d')
    }



# Main admin dashboard
@app.route('/')
def admin_dashboard():
    stats = get_stats()
    categories = get_category_stats()
    recent_orders = get_recent_orders()
    top_products = get_top_products()
    user_activity = get_user_activity()
    sales_data = get_sales_data(30)  # Get sales data for last 30 days
    recent_contacts = get_recent_contacts()  # Get recent contact messages

    return render_template_string('''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Grocery Store Admin Dashboard</title>
        <link rel="icon" type="image/png" href="{{ url_for('static', filename='logo1.webp') }}">
                                  
        <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700&display=swap" rel="stylesheet">
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <style>
            :root {
                --primary: #4CAF50;
                --secondary: #388E3C;
                --accent: #FFC107;
                --light: #E8F5E9;
                --dark: #1B5E20;
                --success: #4CAF50;
                --warning: #FF9800;
                --danger: #F44336;
                --info: #2196F3;
                --card-radius: 16px;
                --section-spacing: 30px;
                --card-spacing: 25px;
            }

            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }

            body {
                font-family: 'Poppins', sans-serif;
                background: #f8fafc;
                color: #333;
                min-height: 100vh;
                padding: 20px;
            }

            .container {
                max-width: 1800px;
                margin: 0 auto;
            }

            header {
                background: linear-gradient(135deg, var(--primary), var(--secondary));
                color: white;
                padding: 25px 35px;
                border-radius: var(--card-radius);
                margin-bottom: var(--section-spacing);
                box-shadow: 0 12px 25px rgba(0, 0, 0, 0.12);
                display: flex;
                justify-content: space-between;
                align-items: center;
            }

            .logo {
                display: flex;
                align-items: center;
                gap: 20px;
            }

            .logo i {
                font-size: 3rem;
                color: var(--accent);
                text-shadow: 0 2px 4px rgba(0,0,0,0.2);
            }

            .logo h1 {
                font-size: 2.4rem;
                font-weight: 600;
                letter-spacing: -0.5px;
            }

            .last-updated {
                font-size: 1.1rem;
                opacity: 0.9;
            }

            .stats-container {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
                gap: 25px;
                margin-bottom: var(--section-spacing);
            }

            .stat-card {
                background: white;
                border-radius: var(--card-radius);
                padding: 30px 25px;
                box-shadow: 0 8px 20px rgba(0, 0, 0, 0.06);
                text-align: center;
                transition: all 0.3s ease;
                position: relative;
                overflow: hidden;
                border: 1px solid #f1f1f1;
            }

            .stat-card::before {
                content: '';
                position: absolute;
                top: 0;
                left: 0;
                width: 6px;
                height: 100%;
                background: var(--primary);
            }

            .stat-card:hover {
                transform: translateY(-8px);
                box-shadow: 0 15px 30px rgba(0, 0, 0, 0.1);
            }

            .stat-card i {
                font-size: 2.8rem;
                margin-bottom: 20px;
                color: var(--primary);
                background: rgba(76, 175, 80, 0.1);
                width: 80px;
                height: 80px;
                display: flex;
                align-items: center;
                justify-content: center;
                border-radius: 50%;
                margin: 0 auto 20px;
            }

            .stat-card h3 {
                font-size: 2.2rem;
                margin-bottom: 12px;
                color: var(--secondary);
                font-weight: 600;
            }

            .stat-card p {
                font-size: 1.1rem;
                color: #666;
                font-weight: 500;
            }

            .dashboard-section {
                background: white;
                border-radius: var(--card-radius);
                padding: var(--card-spacing);
                margin-bottom: var(--section-spacing);
                box-shadow: 0 8px 20px rgba(0, 0, 0, 0.06);
                border: 1px solid #f1f1f1;
            }

            .section-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 30px;
                padding-bottom: 20px;
                border-bottom: 2px solid #f0f5ff;
            }

            .section-header h2 {
                font-size: 1.8rem;
                color: var(--dark);
                display: flex;
                align-items: center;
                gap: 15px;
                font-weight: 600;
            }

            .section-header h2 i {
                color: var(--accent);
                background: rgba(255, 193, 7, 0.15);
                width: 50px;
                height: 50px;
                display: flex;
                align-items: center;
                justify-content: center;
                border-radius: 12px;
            }

            .chart-container {
                height: 320px;
                margin-bottom: 30px;
            }

            .dashboard-grid {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: var(--section-spacing);
            }

            .dashboard-column {
                display: flex;
                flex-direction: column;
                gap: var(--section-spacing);
            }

            .full-width {
                grid-column: 1 / -1;
            }

            .contacts-section {
                display: flex;
                flex-direction: column;
                height: 100%;
            }

            @media (max-width: 1400px) {
                .dashboard-grid {
                    grid-template-columns: 1fr;
                }
            }

            .orders-list, .users-list, .contacts-list {
                max-height: 400px;
                overflow-y: auto;
                padding-right: 10px;
            }

            .order-item, .user-item, .contact-item {
                background: #fafcff;
                border-left: 4px solid var(--primary);
                padding: 25px;
                margin-bottom: 20px;
                border-radius: 14px;
                transition: all 0.3s ease;
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.03);
            }

            .contact-item {
                border-left-color: var(--info);
                background: #f8fbff;
            }

            .order-item:hover, .user-item:hover, .contact-item:hover {
                background: #f1f9ff;
                transform: translateY(-3px);
                box-shadow: 0 8px 20px rgba(0, 0, 0, 0.08);
            }

            .order-header, .user-header, .contact-header {
                display: flex;
                justify-content: space-between;
                margin-bottom: 15px;
                align-items: center;
            }

            .order-id, .contact-id {
                font-weight: 700;
                color: var(--dark);
                font-size: 1.1rem;
            }

            .contact-id {
                color: var(--info);
            }

            .order-amount {
                color: var(--primary);
                font-weight: 700;
                font-size: 1.3rem;
            }

            .order-date, .contact-date {
                font-size: 1rem;
                color: #78909C;
                margin-bottom: 15px;
                display: flex;
                align-items: center;
                gap: 8px;
            }

            .order-date i, .contact-date i {
                color: var(--primary);
            }

            .order-products {
                margin: 15px 0;
                padding-left: 15px;
            }

            .order-product {
                display: flex;
                justify-content: space-between;
                margin-bottom: 10px;
                padding: 10px 0;
                border-bottom: 1px dashed #e0e0e0;
            }

            .order-product:last-child {
                border-bottom: none;
            }

            .user-name, .contact-name {
                font-weight: 700;
                color: var(--dark);
                font-size: 1.2rem;
                margin-bottom: 5px;
            }

            .contact-name {
                color: var(--info);
            }

            .user-email, .contact-email {
                color: var(--primary);
                margin-bottom: 5px;
                display: flex;
                align-items: center;
                gap: 8px;
            }

            .contact-email {
                color: var(--info);
            }

            .contact-phone {
                color: #5a6268;
                margin-bottom: 15px;
                display: flex;
                align-items: center;
                gap: 8px;
                font-weight: 500;
            }

            .contact-subject {
                font-weight: 700;
                margin-bottom: 15px;
                color: var(--dark);
                font-size: 1.1rem;
                background: rgba(33, 150, 243, 0.08);
                padding: 10px 15px;
                border-radius: 8px;
                display: inline-block;
            }

            .contact-message {
                color: #4a5568;
                font-size: 1rem;
                line-height: 1.6;
                padding: 15px;
                background: #f9fbfd;
                border-radius: 10px;
                border: 1px solid #edf2f7;
            }

            .product-grid {
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
                gap: 25px;
                margin-top: 20px;
            }

            .product-card {
                background: white;
                border-radius: 14px;
                overflow: hidden;
                box-shadow: 0 6px 15px rgba(0, 0, 0, 0.08);
                transition: all 0.3s ease;
                border: 1px solid #f1f1f1;
            }

            .product-card:hover {
                transform: translateY(-8px);
                box-shadow: 0 12px 25px rgba(0, 0, 0, 0.12);
            }

            .product-image {
                height: 150px;
                overflow: hidden;
                border-bottom: 1px solid #f0f0f0;
            }

            .product-image img {
                width: 100%;
                height: 100%;
                object-fit: cover;
                transition: transform 0.5s ease;
            }

            .product-card:hover .product-image img {
                transform: scale(1.05);
            }

            .product-info {
                padding: 20px;
            }

            .product-name {
                font-weight: 700;
                margin-bottom: 10px;
                color: var(--dark);
                font-size: 1.1rem;
            }

            .product-stats {
                display: flex;
                justify-content: space-between;
                font-size: 1rem;
            }

            .product-count {
                color: var(--primary);
                font-weight: 700;
            }

            .category-item {
                display: flex;
                justify-content: space-between;
                padding: 20px;
                margin-bottom: 15px;
                background: #fafcff;
                border-radius: 14px;
                border-left: 4px solid var(--primary);
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.03);
                transition: all 0.3s ease;
            }

            .category-item:hover {
                transform: translateY(-3px);
                box-shadow: 0 8px 20px rgba(0, 0, 0, 0.08);
            }

            .category-name {
                font-weight: 600;
                font-size: 1.1rem;
            }

            .category-count {
                background: var(--primary);
                color: white;
                padding: 6px 15px;
                border-radius: 20px;
                font-size: 1rem;
                font-weight: 600;
            }

            footer {
                text-align: center;
                padding: 30px;
                color: #78909C;
                font-size: 1rem;
                margin-top: var(--section-spacing);
            }

            .alert {
                padding: 20px;
                border-radius: 14px;
                margin-bottom: 30px;
                display: flex;
                align-items: center;
                gap: 20px;
                font-size: 1.1rem;
            }

            .alert-success {
                background: #e8f5e9;
                border-left: 6px solid var(--success);
                color: var(--success);
            }

            .alert-danger {
                background: #ffebee;
                border-left: 6px solid var(--danger);
                color: var(--danger);
            }

            .alert i {
                font-size: 1.8rem;
            }

            @media (max-width: 992px) {
                .stats-container {
                    grid-template-columns: 1fr;
                }

                header {
                    flex-direction: column;
                    text-align: center;
                    gap: 20px;
                }

                .logo {
                    justify-content: center;
                }
            }

            /* Sales chart date selector */
            .date-selector {
                display: flex;
                gap: 15px;
                margin-bottom: 20px;
                align-items: center;
            }

            .date-selector select {
                padding: 12px 18px;
                border: 1px solid #e2e8f0;
                border-radius: 10px;
                background: white;
                font-family: 'Poppins', sans-serif;
                font-size: 1rem;
                box-shadow: 0 2px 6px rgba(0, 0, 0, 0.05);
            }

            .date-range {
                font-size: 1rem;
                color: #666;
                margin-left: auto;
                font-weight: 500;
            }

            /* Scrollbar styling */
            ::-webkit-scrollbar {
                width: 8px;
                height: 8px;
            }

            ::-webkit-scrollbar-track {
                background: #f1f1f1;
                border-radius: 10px;
            }

            ::-webkit-scrollbar-thumb {
                background: #c5c5c5;
                border-radius: 10px;
            }

            ::-webkit-scrollbar-thumb:hover {
                background: #a8a8a8;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <header>
                <div class="logo">
                    <i class="fas fa-shopping-basket"></i>
                    <h1>Grocery Store Admin Dashboard</h1>
                </div>
                <div class="last-updated">
                    <span>Last updated: {{ current_time }}</span>
                </div>
            </header>

            {% with messages = get_flashed_messages(with_categories=true) %}
                {% if messages %}
                    {% for category, message in messages %}
                        <div class="alert alert-{{ category }}">
                            <i class="fas fa-{% if category == 'success' %}check-circle{% else %}exclamation-circle{% endif %}"></i>
                            {{ message }}
                        </div>
                    {% endfor %}
                {% endif %}
            {% endwith %}


            <div class="stats-container">
                <div class="stat-card">
                    <i class="fas fa-shopping-cart"></i>
                    <h3>{{ stats.total_orders }}</h3>
                    <p>Total Orders</p>
                </div>
                <div class="stat-card">
                    <i class="fas fa-users"></i>
                    <h3>{{ stats.total_users }}</h3>
                    <p>Registered Users</p>
                </div>
                <div class="stat-card">
                    <i class="fas fa-box"></i>
                    <h3>{{ stats.total_products }}</h3>
                    <p>Products in Store</p>
                </div>
                <div class="stat-card">
                    <i class="fas fa-money-bill-wave"></i>
                    <h3>₹{{ stats.total_revenue }}</h3>
                    <p>Total Revenue</p>
                </div>
                <div class="stat-card">
                    <i class="fas fa-envelope"></i>
                    <h3>{{ stats.total_contacts }}</h3>
                    <p>Contact Messages</p>
                </div>
                <div class="stat-card">
                    <i class="fas fa-chart-line"></i>
                    <h3>₹{{ stats.avg_order_value }}</h3>
                    <p>Average Order Value</p>
                </div>
            </div>

            <!-- Sales Chart Section -->
            <div class="dashboard-section full-width">
                <div class="section-header">
                    <h2><i class="fas fa-chart-line"></i> Sales Trend</h2>
                    <div class="date-selector">
                        <select id="timePeriod">
                            <option value="7">Last 7 Days</option>
                            <option value="30" selected>Last 30 Days</option>
                            <option value="90">Last 90 Days</option>
                        </select>
                        <div class="date-range">
                            {{ sales_data.min_date }} to {{ sales_data.max_date }}
                        </div>
                    </div>
                </div>
                <div class="chart-container">
                    <canvas id="salesChart"></canvas>
                </div>
            </div>

            <div class="dashboard-grid">
                <!-- Left Column -->
                <div class="dashboard-column">
                    <!-- Category Section -->
                    <div class="dashboard-section">
                        <div class="section-header">
                            <h2><i class="fas fa-chart-pie"></i> Products by Category</h2>
                        </div>
                        <div class="chart-container">
                            <canvas id="categoryChart"></canvas>
                        </div>

                        <div class="section-header">
                            <h2><i class="fas fa-list"></i> Category Breakdown</h2>
                        </div>
                        <div class="categories-list">
                            {% for category in categories %}
                                <div class="category-item">
                                    <span class="category-name">{{ category['category'] }}</span>
                                    <span class="category-count">{{ category['count'] }} products</span>
                                </div>
                            {% endfor %}
                        </div>
                    </div>

                    <!-- Top Products Section -->
                    <div class="dashboard-section">
                        <div class="section-header">
                            <h2><i class="fas fa-star"></i> Top Selling Products</h2>
                        </div>
                        <div class="product-grid">
                            {% for product in top_products %}
                                <div class="product-card">
                                    <div class="product-image">
                                        <img src="{{ product['image_path'] }}" alt="{{ product['name'] }}">
                                    </div>
                                    <div class="product-info">
                                        <div class="product-name">{{ product['name'] }}</div>
                                        <div class="product-stats">
                                            <span>Sold: <strong class="product-count">{{ product['count'] }}</strong></span>
                                            <span>₹{{ product['price'] }}</span>
                                        </div>
                                    </div>
                                </div>
                            {% else %}
                                <p>No product data available.</p>
                            {% endfor %}
                        </div>
                    </div>
                </div>

                <!-- Right Column -->
                <div class="dashboard-column">
                    <!-- Recent Orders Section -->
                    <div class="dashboard-section">
                        <div class="section-header">
                            <h2><i class="fas fa-receipt"></i> Recent Orders</h2>
                        </div>
                        <div class="orders-list">
                            {% for order in recent_orders %}
                                <div class="order-item">
                                    <div class="order-header">
                                        <div class="order-id">Order #{{ order['order_id'] }}</div>
                                        <div class="order-amount">₹{{ order['total_amount'] }}</div>
                                    </div>
                                    <div class="order-date">
                                        <i class="fas fa-calendar-alt"></i> {{ order['order_date'] }} by {{ order['user_name'] }}
                                    </div>
                                    <div class="order-products">
                                        {% for product in order['products'] %}
                                            <div class="order-product">
                                                <span>{{ product['name'] }} (×{{ product['quantity'] }})</span>
                                                <span>₹{{ product['price'] * product['quantity'] }}</span>
                                            </div>
                                        {% endfor %}
                                    </div>
                                </div>
                            {% else %}
                                <p>No recent orders found.</p>
                            {% endfor %}
                        </div>
                    </div>

                    <!-- User Activity Section -->
                    <div class="dashboard-section">
                        <div class="section-header">
                            <h2><i class="fas fa-user-clock"></i> User Activity</h2>
                        </div>
                        <div class="users-list">
                            <h3 style="margin-bottom: 20px; font-size: 1.3rem; color: var(--dark);">Most Active Users</h3>
                            {% for user in user_activity.active_users %}
                                <div class="user-item">
                                    <div class="user-header">
                                        <div class="user-name">{{ user['name'] }}</div>
                                        <div class="order-count">{{ user['order_count'] }} orders</div>
                                    </div>
                                    <div class="user-email">
                                        <i class="fas fa-envelope"></i> {{ user['email'] }}
                                    </div>
                                </div>
                            {% endfor %}

                            <h3 style="margin-top: 30px; margin-bottom: 20px; font-size: 1.3rem; color: var(--dark);">Recently Registered</h3>
                            {% for user in user_activity.recent_users %}
                                <div class="user-item">
                                    <div class="user-header">
                                        <div class="user-name">{{ user['name'] }}</div>
                                    </div>
                                    <div class="user-email">
                                        <i class="fas fa-envelope"></i> {{ user['email'] }}
                                    </div>
                                </div>
                            {% endfor %}
                        </div>
                    </div>

                    <!-- Contact Messages Section -->
                    <div class="dashboard-section contacts-section">
                        <div class="section-header">
                            <h2><i class="fas fa-envelope"></i> Recent Contact Messages</h2>
                        </div>
                        <div class="contacts-list">
                            {% for contact in recent_contacts %}
                                <div class="contact-item">
                                    <div class="contact-header">
                                        <div class="contact-id">Message #{{ contact['id'] }}</div>
                                    </div>
                                    <div class="contact-date">
                                        <i class="fas fa-clock"></i> {{ contact['timestamp'] }}
                                    </div>
                                    <div class="contact-name">{{ contact['name'] }}</div>
                                    <div class="contact-email">
                                        <i class="fas fa-envelope"></i> {{ contact['email'] }}
                                    </div>
                                    {% if contact['phone'] %}
                                        <div class="contact-phone">
                                            <i class="fas fa-phone"></i> {{ contact['phone'] }}
                                        </div>
                                    {% endif %}
                                    <div class="contact-subject">{{ contact['subject'] }}</div>
                                    <div class="contact-message">{{ contact['message'] }}</div>
                                </div>
                            {% else %}
                                <p>No contact messages found.</p>
                            {% endfor %}
                        </div>
                    </div>
                </div>
            </div>

            <footer>
                <p>Grocery Store Admin Dashboard &copy; {{ current_year }} | All rights reserved</p>
            </footer>
        </div>

        <script>
            // Sales Chart
            const salesCtx = document.getElementById('salesChart').getContext('2d');
            const salesChart = new Chart(salesCtx, {
                type: 'line',
                data: {
                    labels: {{ sales_data.labels | tojson }},
                    datasets: [{
                        label: 'Daily Sales (₹)',
                        data: {{ sales_data.data | tojson }},
                        backgroundColor: 'rgba(76, 175, 80, 0.15)',
                        borderColor: 'rgba(76, 175, 80, 1)',
                        borderWidth: 3,
                        pointBackgroundColor: 'rgba(76, 175, 80, 1)',
                        pointRadius: 4,
                        pointHoverRadius: 7,
                        tension: 0.3,
                        fill: true
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: {
                            beginAtZero: true,
                            grid: {
                                color: 'rgba(0,0,0,0.05)'
                            },
                            title: {
                                display: true,
                                text: 'Revenue (₹)',
                                font: {
                                    size: 14,
                                    weight: 'bold'
                                }
                            },
                            ticks: {
                                font: {
                                    size: 12
                                }
                            }
                        },
                        x: {
                            grid: {
                                display: false
                            },
                            ticks: {
                                maxTicksLimit: 10,
                                font: {
                                    size: 12
                                }
                            }
                        }
                    },
                    plugins: {
                        legend: {
                            display: true,
                            position: 'top',
                            labels: {
                                font: {
                                    size: 14,
                                    weight: 'bold'
                                }
                            }
                        },
                        tooltip: {
                            mode: 'index',
                            intersect: false,
                            backgroundColor: 'rgba(0,0,0,0.8)',
                            padding: 15,
                            titleFont: {
                                size: 14
                            },
                            bodyFont: {
                                size: 14
                            },
                            callbacks: {
                                label: function(context) {
                                    return `₹${context.parsed.y}`;
                                }
                            }
                        }
                    },
                    interaction: {
                        intersect: false,
                        mode: 'nearest'
                    }
                }
            });

            // Category Chart
            const categoryCtx = document.getElementById('categoryChart').getContext('2d');
            const categoryChart = new Chart(categoryCtx, {
                type: 'doughnut',
                data: {
                    labels: [
                        {% for category in categories %}
                            '{{ category['category'] }}',
                        {% endfor %}
                    ],
                    datasets: [{
                        data: [
                            {% for category in categories %}
                                {{ category['count'] }},
                            {% endfor %}
                        ],
                        backgroundColor: [
                            '#4CAF50', '#FFC107', '#2196F3', '#9C27B0', '#FF5722', 
                            '#00BCD4', '#795548', '#607D8B', '#8BC34A', '#E91E63'
                        ],
                        borderWidth: 1
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'right',
                            labels: {
                                font: {
                                    size: 13
                                }
                            }
                        },
                        tooltip: {
                            padding: 12,
                            bodyFont: {
                                size: 14
                            }
                        }
                    },
                    cutout: '60%'
                }
            });

            // Time period selector for sales chart
            document.getElementById('timePeriod').addEventListener('change', function() {
                const days = this.value;
                fetch(`/sales-data?days=${days}`)
                    .then(response => response.json())
                    .then(data => {
                        // Update the date range display
                        document.querySelector('.date-range').textContent = 
                            `${data.min_date} to ${data.max_date}`;

                        // Update the chart
                        salesChart.data.labels = data.labels;
                        salesChart.data.datasets[0].data = data.data;
                        salesChart.update();
                    });
            });
        </script>
    </body>
    </html>
    ''',
                                  stats=get_stats(),
                                  categories=get_category_stats(),
                                  recent_orders=get_recent_orders(),
                                  top_products=get_top_products(),
                                  user_activity=get_user_activity(),
                                  sales_data=get_sales_data(30),
                                  recent_contacts=get_recent_contacts(),
                                  current_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                  current_year=datetime.now().year)


# API endpoint for sales data
@app.route('/sales-data')
def sales_data_api():
    days = request.args.get('days', default=30, type=int)
    return jsonify(get_sales_data(days))


if __name__ == '__main__':
    port = int(os.environ.get('PORT', os.environ.get('FLASK_RUN_PORT', 5000)))
    app.run(debug=True, port=port)