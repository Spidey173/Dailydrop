# 🛒 DailyDrop — Full-Stack Grocery Delivery Platform

> **Target Role**: Junior Backend Developer / Python Full-Stack Engineer  
> **Core Deliverable**: Production-ready grocery delivery platform featuring atomic inventory checkout transactions, session-based cart persistence, modular Blueprint + Service architecture, and 42 automated Pytest unit tests.

[![Live Demo](https://img.shields.io/badge/Live%20Demo-dailydrop17.vercel.app-red?style=flat-square&logo=vercel)](https://dailydrop17.vercel.app/)
[![Tests](https://img.shields.io/badge/Pytest-42%20Passed-brightgreen?style=flat-square&logo=pytest)](tests/)
[![Backend](https://img.shields.io/badge/Backend-Python%20%7C%20Flask-blue?style=flat-square&logo=python)](app.py)
[![Database](https://img.shields.io/badge/Database-PostgreSQL%20(Neon)-336791?style=flat-square&logo=postgresql&logoColor=white)](database.py)
[![Cache](https://img.shields.io/badge/Cache-Redis%20(Fallback%20Safe)-DC382D?style=flat-square&logo=redis&logoColor=white)](services/redis_service.py)
[![License](https://img.shields.io/badge/License-MIT-lightgrey?style=flat-square)](LICENSE)

🔗 **[Live Storefront](https://dailydrop17.vercel.app/)** | 🛡️ **[Admin Portal](https://dailydrop17.vercel.app/admin_login)** | 📦 **[GitHub Repository](https://github.com/Spidey173/Dailydrop)**

---

## ⚡ Standout Metrics At A Glance

| 📦 Catalog Scale | 🧪 Test Suite | 🛡️ Concurrency Safety | ⚡ Live Search | 🌐 Deployment |
| :---: | :---: | :---: | :---: | :---: |
| **200+ Products across 10 Categories** | **42 / 42 Pytest Tests Passed** | **Atomic DB Transactions (Zero Oversell)** | **Sub-Second Client-Side Filtering** | **Vercel Serverless WSGI + Neon Cloud DB** |

---

## 🏆 3 Core Engineering Highlights

### 1. 🛡️ Atomic Inventory Decrementing & Concurrency Protection
* **Problem**: In e-commerce checkout flows, concurrent orders can lead to race conditions where the same remaining stock is sold twice (negative inventory).
* **Implementation**: Stock verification and decrementing execute within an atomic database transaction. If any item in the cart lacks sufficient quantity, the transaction rolls back cleanly, protecting inventory consistency.
* **Resilience**: Integrated Redis-based atomic decrement helper scripts for high-concurrency environments, paired with graceful database-level transaction fallbacks.

### 2. 🏛️ Modular Service-Oriented Monolith
* **Problem**: Large Flask codebases often become unmaintainable when SQL queries and business logic are mixed directly into HTTP route handlers.
* **Implementation**: Architected with Flask **Blueprints** (`auth`, `cart`, `products`, `admin`) strictly separated from a dedicated **Service Layer** (`order_service.py`, `auth_service.py`, `product_service.py`, `payment_service.py`).
* **Benefit**: Enables isolated unit testing, easy feature additions, and clean separation of concerns.

### 3. 🔄 Resilient Dual-Engine Database & Cache Fallback
* **Problem**: Cloud services occasionally fail or disconnect; local development shouldn't require spinning up remote cloud instances.
* **Implementation**: Configured for Neon Serverless PostgreSQL with connection pooling (`psycopg2`) in production, with seamless zero-config SQLite fallback for local test automation and CI/CD pipelines.
* **Cache Safety**: Read-through Redis caching accelerates frequent catalog queries, designed to degrade gracefully to direct database queries without throwing errors if the cache is unreachable.

---

## 🔑 Demo Access Accounts

Ready-to-use accounts for immediate testing:

| Role | Email | Password | Access URL |
| :--- | :--- | :--- | :--- |
| **Customer** | `demo_dailydrop@gmail.com` | `Demouser@123` | [`/login`](https://dailydrop17.vercel.app/login) |
| **Admin** | `admin_dailydrop@gmail.com` | `Dailydrop@173` | [`/admin_login`](https://dailydrop17.vercel.app/admin_login) |

---

## 🛍️ What the Application Does

### Customer Storefront
* **Product Catalog**: Over 200+ daily grocery items organized into 10 practical categories (Fruits & Vegetables, Dairy & Breakfast, Snacks, Beverages, Household, etc.).
* **Live Search & Autocomplete**: Instant client-side search to filter and view items on the fly without repeated page reloads.
* **Cart & Wishlist**: Interactive cart management and wishlist persistence linked to user sessions (supporting both guest and authenticated states).
* **Order Placement & Payments**: Seamless checkout supporting Cash on Delivery (COD) and Razorpay payment verification.
* **Order Tracking**: Itemized order history with live status updates (`Processing` → `Shipped` → `Delivered`).

### Admin Dashboard (`/admin_login`)
* **Store Analytics**: Real-time overview of total revenue, order count, and registered users.
* **Catalog Management**: Admin controls to adjust item prices, restock quantities, or toggle item availability.
* **Order Fulfillment**: Workflow controls to advance and manage customer order lifecycles.

---

## 🛠️ Technical Stack (Secondary Details)

* **Backend**: Python 3.10+, Flask (Application Factory, Blueprints, Jinja2)
* **Architecture**: Service-Oriented Layer (`services/`), Repository Pattern
* **Database**: PostgreSQL (Neon Serverless, Connection Pooling with `psycopg2`), SQLite (Local/CI)
* **Caching**: Redis (Optional read-through catalog caching & atomic decrement helpers)
* **Security & Auth**: Session Cookies, Bcrypt Password Hashing, Role-Based Route Guards (`@admin_required`)
* **Frontend**: HTML5, Vanilla CSS3, JavaScript (ES6+), Bootstrap 5
* **Testing & CI**: Pytest (42 automated unit & integration tests), GitHub Actions CI
* **Deployment**: Vercel Serverless WSGI

---

## 📁 Project Structure

```
Daily-Drop/
├── app.py                  # Application factory (create_app)
├── database.py             # Database connection pooling & schema execution
├── config.py               # Central environment configuration
├── blueprints/             # Route controllers
│   ├── auth.py             # User signup, login, and session handling
│   ├── cart.py             # Cart operations & checkout endpoints
│   ├── products.py         # Catalog views & search endpoints
│   └── admin.py            # Admin dashboard & inventory controls
├── services/               # Core business logic layer
│   ├── auth_service.py     # Password hashing & user validation
│   ├── order_service.py    # Order creation, items normalization, stock updates
│   ├── product_service.py  # Catalog querying & admin updates
│   ├── payment_service.py  # Razorpay order generation & signature verification
│   └── redis_service.py    # Read-through cache & atomic stock decrement helpers
├── static/                 # Stylesheets, UI icons, and product images
├── templates/              # Jinja2 HTML templates
└── tests/                  # 42 automated Pytest test suites
```

---

## 🧪 Automated Testing

The project includes 42 automated unit and integration tests covering authentication, cart calculations, atomic checkout, admin controls, and payment verification:

```bash
# Run the complete test suite locally
pytest -v
```

All 42 tests execute automatically in GitHub Actions CI across Python matrix environments on every commit.

---

## 🚀 Local Development Setup

```bash
# 1. Clone repository
git clone https://github.com/Spidey173/Dailydrop.git
cd Dailydrop

# 2. Set up virtual environment
python3 -m venv venv
source venv/bin/activate
# Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment (Optional - defaults to local SQLite if omitted)
cp .env.example .env

# 5. Run local development server
python app.py
```
Open [http://localhost:5000](http://localhost:5000) in your browser.

---

## 💡 Interview Defense Guide (30-Second Summary)

> *"DailyDrop is a full-stack e-commerce web application built with Flask and PostgreSQL. I led a 4-person intern team to build it during my PyGenicArc internship.*  
>  
> *Rather than putting SQL inside route functions, I architected it with Flask Blueprints and a dedicated Service layer. The key technical challenge was **data consistency**: when customers checkout, stock decrements run inside an atomic database transaction to prevent race conditions and overselling. The project has 42 automated Pytest tests, dual PostgreSQL/SQLite support, and is deployed live on Vercel."*

---

## 📄 License
This project is open-source under the [MIT License](LICENSE).
