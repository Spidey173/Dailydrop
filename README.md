# DailyDrop 🛒 — Full-Stack Quick-Commerce Web Application

[![CI Pipeline](https://github.com/Spidey173/Dailydrop/actions/workflows/ci.yml/badge.svg)](https://github.com/Spidey173/Dailydrop/actions)
[![Backend](https://img.shields.io/badge/Backend-Python%20%7C%20Flask-blue?style=flat-square&logo=python)](app.py)
[![Database](https://img.shields.io/badge/Database-PostgreSQL%20(Neon)-336791?style=flat-square&logo=postgresql&logoColor=white)](database.py)
[![Cache](https://img.shields.io/badge/Cache-Redis%20(Fallback%20Safe)-DC382D?style=flat-square&logo=redis&logoColor=white)](services/redis_service.py)
[![License](https://img.shields.io/badge/License-MIT-lightgrey?style=flat-square)](LICENSE)

🔗 **[Live Storefront](https://dailydrop17.vercel.app/)** | 🛡️ **[Admin Portal](https://dailydrop17.vercel.app/admin_login)** | 📦 **[GitHub Repository](https://github.com/Spidey173/Dailydrop)**

---

## ⚡ Standout Metrics At A Glance

| 📦 Catalog Scale | 🧪 Test Suite | 🛡️ Concurrency & Integrity | ⚡ Live Search | 🌐 Deployment |
| :---: | :---: | :---: | :---: | :---: |
| **200+ Products across 10 Categories** | **49 / 49 Pytest Tests Passed (100%)** | **Atomic DB Transactions & Authoritative Pricing** | **Sub-Second Client-Side Filtering** | **Vercel Serverless WSGI + Neon Cloud DB** |

---

## 🏆 3 Core Engineering Highlights

### 1. 🛡️ Atomic Inventory Decrementing & Price Integrity
* **Problem**: Concurrent checkouts can cause race conditions leading to overselling (negative stock), and client-side cart tampering can spoof lower order amounts.
* **Implementation**: Stock decrementing is executed within an atomic database transaction (`UPDATE products SET stock = stock - %s WHERE stock >= %s`). Authoritative product prices are looked up directly from the database during checkout, overriding client-side payload tampering.
* **Resilience**: Redis-based atomic decrement scripts provide microsecond concurrency controls, with fallback to relational database ACID transactions.

### 2. 🏛️ Modular Service-Oriented Monolith
* **Problem**: Flask codebases quickly degrade in maintainability when SQL queries, validation, and HTTP routing are blended in view handlers.
* **Implementation**: Architected using Flask **Blueprints** (`auth`, `cart`, `products`, `admin`) strictly decoupled from a dedicated **Service Layer** (`order_service.py`, `auth_service.py`, `product_service.py`, `payment_service.py`, `idempotency_service.py`).
* **Benefit**: Allows fast, isolated unit testing, predictable refactoring, and clear separation of concerns.

### 3. 🔒 Defensive Security Hardening
* **CSRF Protection**: Flask-WTF tokens enforced across all state-mutating customer and admin endpoints with automatic JavaScript fetch header injection; server-to-server payment webhooks are protected with cryptographic HMAC-SHA256 signatures.
* **Session & Auth Hardening**: Complete session clearance on login and logout prevents session fixation attacks. Passwords use Werkzeug's secure `scrypt` hashing.
* **Safe Ingestion & Headers**: Strict image extension whitelisting (`.png`, `.jpg`, `.jpeg`, `.webp`) blocks dangerous uploads, and defensive HTTP security headers (`nosniff`, `SAMEORIGIN`, strict-origin-when-cross-origin) are applied to all responses.

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
* **Order Placement & Payments**: Checkout supporting Cash on Delivery (COD) with idempotency protection and Razorpay payment signature verification.
* **Order Tracking**: Itemized order history with sequential user order numbers and live status updates (`Processing` → `Shipped` → `Delivered`).

### Admin Dashboard (`/admin_login`)
* **Store Analytics**: Real-time overview of total revenue, order count, and registered users.
* **Catalog Management**: Admin controls to adjust item prices, restock quantities, or toggle item availability with extension-validated image uploads.
* **Order Fulfillment**: Workflow controls to advance customer order lifecycles with terminal status protection.

---

## 🛠️ Technical Stack (Secondary Details)

* **Backend**: Python 3.10+, Flask (Application Factory, Blueprints, Jinja2)
* **Architecture**: Service-Oriented Layer (`services/`), Repository Pattern
* **Database**: PostgreSQL (Neon Serverless, Connection Pooling with `psycopg2`), SQLite (Local In-Memory Test Fixture)
* **Caching & Queue**: Redis (Optional read-through catalog caching & atomic stock decrement helpers)
* **Security & Auth**: Flask-WTF CSRF Tokens, Werkzeug Scrypt Password Hashing, Role-Based Route Guards (`@admin_required`), Defensive Security Headers
* **Frontend**: HTML5, Vanilla CSS3, JavaScript (ES6+), Bootstrap 5
* **Testing & CI**: Pytest (49 automated unit, integration & security regression tests), GitHub Actions CI
* **Deployment**: Vercel Serverless WSGI

---

## 📁 Project Structure

```
Daily-Drop/
├── app.py                  # Application factory (create_app) & security headers
├── database.py             # Database connection pooling & schema execution
├── config.py               # Central environment configuration & fail-fast validation
├── blueprints/             # Route controllers
│   ├── auth.py             # User signup, login, session clearance
│   ├── cart.py             # Cart operations, checkout & Razorpay webhooks
│   ├── products.py         # Catalog views & search endpoints
│   └── admin.py            # Admin dashboard, order fulfillment, upload controls
├── services/               # Core business logic layer
│   ├── auth_service.py     # Password hashing & user validation
│   ├── order_service.py    # Order creation, items normalization, stock updates
│   ├── product_service.py  # Catalog querying & admin updates
│   ├── payment_service.py  # Authoritative price resolution & HMAC verification
│   ├── idempotency_service.py # Redis idempotency tokens & user isolation
│   └── redis_service.py    # Read-through cache & atomic stock decrement helpers
├── static/                 # Stylesheets, UI icons, and product images
├── templates/              # Jinja2 HTML templates with CSRF token meta tags
└── tests/                  # 49 automated Pytest test suites (including security regression)
```

---

## 🧪 Automated Testing

The project includes 49 automated unit, integration, and security regression tests covering authentication, cart calculations, price tampering prevention, atomic checkout, admin controls, and payment verification:

```bash
# Run the complete test suite locally
pytest -v
```

All 49 tests execute automatically in GitHub Actions CI across Python matrix environments on every commit.

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

# 4. Configure environment (Generate a secure 32-byte secret key)
python3 -c "import secrets; print(secrets.token_hex(32))"
cp .env.example .env

# 5. Run local development server
python app.py
```
Open [http://localhost:5000](http://localhost:5000) in your browser.

---

## 💡 Interview Defense Guide (30-Second Summary)

> *"DailyDrop is a full-stack e-commerce web application built with Flask and PostgreSQL. I led a 4-person intern team to build it during my PyGenicArc internship.*  
>  
> *Rather than putting SQL inside route functions, I architected it with Flask Blueprints and a dedicated Service layer. The key technical challenge was **data consistency and checkout integrity**: stock decrements run inside an atomic database transaction to prevent overselling, and prices are resolved authoritatively from the database to prevent client tampering. The project has 49 automated Pytest tests, dual PostgreSQL/SQLite support, and is deployed live on Vercel."*

---

## 📄 License
This project is open-source under the [MIT License](LICENSE).
