# DailyDrop 🛒 — Full-Stack Quick-Commerce Web Application

[![CI Pipeline](https://github.com/Spidey173/Dailydrop/actions/workflows/ci.yml/badge.svg)](https://github.com/Spidey173/Dailydrop/actions)
[![Tests](https://img.shields.io/badge/Pytest-61%20Passed-brightgreen?style=flat-square&logo=pytest)](tests/)
[![Backend](https://img.shields.io/badge/Backend-Python%20%7C%20Flask-blue?style=flat-square&logo=python)](app.py)
[![Database](https://img.shields.io/badge/Database-PostgreSQL%20(Neon)-336791?style=flat-square&logo=postgresql&logoColor=white)](database.py)
[![Cache](https://img.shields.io/badge/Cache-Redis%20(Fallback%20Safe)-DC382D?style=flat-square&logo=redis&logoColor=white)](services/redis_service.py)
[![License](https://img.shields.io/badge/License-MIT-lightgrey?style=flat-square)](LICENSE)

🔗 **[Live Storefront](https://dailydrop17.vercel.app/)** | 🛡️ **[Admin Portal](https://dailydrop17.vercel.app/admin_login)** | 🩺 **[Health Status](https://dailydrop17.vercel.app/healthz)** | 📦 **[GitHub Repository](https://github.com/Spidey173/Dailydrop)**

---

## ⚡ Standout Metrics At A Glance

| 📦 Catalog Scale | 🧪 Test Suite | 🛡️ Concurrency & Integrity | ⚡ Live Search | 🌐 Deployment |
| :---: | :---: | :---: | :---: | :---: |
| **200+ Products across 10 Categories** | **61 / 61 Pytest Tests Passed (100%)** | **Server-Authoritative Pricing & Atomic Transactions** | **Sub-Second Client-Side Filtering** | **Vercel Serverless WSGI + Neon Cloud DB** |

---

## 🏆 5 Core Engineering Highlights

### 1. 🛡️ Server-Authoritative Checkout & Catalog Integrity
* **Problem**: Untrusted client-side payloads can forge item prices, submit nonexistent or outdated product IDs, or cause negative stock under concurrent checkout spikes.
* **Implementation**: Checkout is 100% server-authoritative. The backend validates every cart item against the live database catalog, strictly rejecting unlisted items. Product prices, discounts, delivery fees, and order totals are recomputed from database records and saved as immutable snapshots into `orders` and `order_items`.
* **Atomic Concurrency**: Inventory decrements use conditional SQL (`UPDATE products SET stock = stock - %s WHERE stock >= %s`) within an atomic transaction. If any single item lacks sufficient stock, the entire checkout rolls back cleanly.

### 2. 💳 Strict Payment Lifecycle & State Machine
* **Pending Order Ownership**: Payment verification (`/api/verify-payment`) strictly verifies that the order exists in `pending_orders` and belongs to the authenticated user's session before confirming payment or mutating inventory.
* **Webhook Idempotency & Replay Protection**: The Razorpay webhook handler cryptographically verifies HMAC-SHA256 signatures and handles duplicate or out-of-order delivery gracefully without regressing downstream fulfillment status.
* **Finite State Machine (FSM)**: Orders follow a strict progression (`Created` → `Processing` → `Packed` → `Shipped` → `Out for Delivery` → `Delivered`). Terminal states (`Delivered`, `Cancelled`) are immutable and cannot be updated.

### 3. 🏛️ Service-Oriented Architecture & Versioned Migrations
* **Decoupled Architecture**: Routes in Flask **Blueprints** (`auth`, `cart`, `products`, `admin`) delegate all business logic to a dedicated **Service Layer** (`order_service.py`, `auth_service.py`, `product_service.py`, `payment_service.py`, `idempotency_service.py`).
* **Versioned Database Migrations**: Incremental schema changes are managed via versioned migration scripts in `migrations/` and applied idempotently via `python -m migrations.runner`, recording execution in the `schema_migrations` audit table.
* **Dead Code Elimination**: Monolithic prototypes and redundant endpoints have been eliminated in favor of clean RESTful controllers and service helpers.

### 4. 🔒 Defensive Security & Redacted Structured Logging
* **CSRF & Session Security**: Flask-WTF CSRF tokens are validated across all state-mutating requests with automated JavaScript meta injection. Sessions are regenerated upon login/logout to prevent session fixation.
* **Structured & Sanitized Logging**: A custom `SanitizingLogFormatter` scrubs passwords, session secrets, API keys, webhook signatures, and payment details from application logs across stdout and file handlers.
* **Defensive HTTP Headers**: Enforces `X-Content-Type-Options: nosniff`, `X-Frame-Options: SAMEORIGIN`, and strict cookie flags (`HttpOnly`, `SameSite=Lax`, `Secure` in production).

### 5. 🩺 Production Observability & Health Monitoring
* **Liveness & Readiness Probes**: `/healthz` and `/api/v1/health` provide real-time diagnostics on database connectivity, round-trip query latency, Redis cache availability, storage mode, and background queue status.
* **Hosting Alignment**: Gracefully detects serverless environments (Vercel) vs persistent containers. Ephemeral local uploads are safely blocked (`DISABLE_FILE_UPLOADS`) in serverless demos with clean HTTP 400 feedback.

---

## 🔑 Demo Access Accounts

Ready-to-use accounts for immediate testing:

| Role | Email | Password | Access URL |
| :--- | :--- | :--- | :--- |
| **Customer** | `demo_dailydrop@gmail.com` | `Demouser@123` | [`/login`](https://dailydrop17.vercel.app/login) |
| **Admin** | `admin_dailydrop@gmail.com` | `Dailydrop@173` | [`/admin_login`](https://dailydrop17.vercel.app/admin_login) |

> [!NOTE]
> **Sandbox Credentials**: In demo environments, payments run in Razorpay Test Mode using sandbox credentials (`rzp_test_...`). No real money is charged, and test cards or simulated UPI IDs can be used. In a live production deployment, replace with production keys and set `RAZORPAY_WEBHOOK_SECRET`.

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

## 🛠️ Technical Stack

* **Backend**: Python 3.10+, Flask (Application Factory, Blueprints, Jinja2)
* **Architecture**: Service-Oriented Layer (`services/`), Repository Pattern
* **Database**: PostgreSQL (Neon Serverless, Connection Pooling with `psycopg2`), SQLite (Deterministic In-Memory Test Fixture)
* **Migrations**: Custom versioned migration runner (`migrations/`) with `schema_migrations` audit tracking
* **Caching & Queue**: Redis (Read-through catalog caching, atomic stock decrement helpers, background queue)
* **Security & Auth**: Flask-WTF CSRF Tokens, Werkzeug Scrypt Password Hashing, Role-Based Route Guards (`@admin_required`), Defensive Security Headers
* **Frontend**: HTML5, Vanilla CSS3, JavaScript (ES6+), Bootstrap 5
* **Testing & CI**: Pytest (61 automated unit, integration, concurrency & security regression tests), GitHub Actions CI (matrix across Python 3.10, 3.11, 3.12), Flake8 Linting
* **Deployment**: Vercel Serverless WSGI (demo storefront) / Docker & Procfile compatible (production worker PaaS)

---

## 📁 Project Structure

```
Daily-Drop/
├── app.py                  # Application factory (create_app), health routes & security headers
├── database.py             # Database connection pooling & schema execution
├── config.py               # Central environment configuration & fail-fast validation
├── worker.py               # Background transactional outbox worker
├── Procfile                # Production process specification (web + background worker)
├── blueprints/             # Route controllers
│   ├── auth.py             # User signup, login, session clearance
│   ├── cart.py             # Server-authoritative checkout & Razorpay webhooks
│   ├── products.py         # Catalog views & search endpoints
│   ├── admin.py            # Admin dashboard, order fulfillment, upload controls
│   └── main.py             # Public pages & health check endpoints (/healthz)
├── services/               # Core business logic layer
│   ├── auth_service.py     # Password hashing & user validation
│   ├── order_service.py    # Order creation, items normalization, FSM status transitions
│   ├── product_service.py  # Catalog querying & admin updates
│   ├── payment_service.py  # Authoritative price resolution & HMAC verification
│   ├── idempotency_service.py # Redis idempotency tokens & user isolation
│   └── redis_service.py    # Read-through cache & atomic stock decrement helpers
├── migrations/             # Versioned SQL migrations & runner
│   ├── 001_initial_schema.sql
│   ├── 002_add_order_items_and_pending_orders.sql
│   ├── 003_add_outbox_events_and_indexes.sql
│   ├── 004_state_machine_and_inventory_checks.sql
│   └── runner.py           # Idempotent migration runner (python -m migrations.runner)
├── static/                 # Stylesheets, UI icons, and product images
├── templates/              # Jinja2 HTML templates with CSRF token meta tags
└── tests/                  # 61 automated Pytest test suites (unit, integration, security)
```

---

## 🧪 Automated Testing & CI

The project includes **61 automated tests** covering authentication, cart calculations, forged price rejection, unknown product blocking, atomic checkout, stock race conditions, payment signature verification, webhook idempotency, and state machine validation:

```bash
# Run the complete test suite locally
pytest -v

# Run linting and static syntax checks
flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics --exclude=venv,.venv,docs
```

All 61 tests run completely offline against an in-memory SQLite fixture with zero skips, executing in ~25s in GitHub Actions CI across Python 3.10, 3.11, and 3.12.

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

# 5. Run database migrations
python -m migrations.runner

# 6. Run local development server
python app.py
```
Open [http://localhost:5000](http://localhost:5000) in your browser.

---

## 🌐 Deployment Architecture Options

### A. Vercel Serverless (Current Demo Setup)
* **Frontend & Web Routing**: Deployed on Vercel Serverless WSGI.
* **Database**: Neon Serverless PostgreSQL with connection pooling.
* **Storage Consideration**: Vercel lambdas feature an ephemeral, read-only filesystem. File uploads in the demo are gracefully disabled (`DISABLE_FILE_UPLOADS=true`) with user-friendly error handling.
* **Worker Note**: Background outbox events are synchronously dispatched or processed on a fallback basis.

### B. Production Container PaaS (Render / Railway / AWS ECS)
* **Web Service**: Runs `gunicorn app:app -w 4 -k gthread --threads 2`.
* **Worker Service**: Runs `python worker.py` continuously processing transactional outbox events from `outbox_events` and Redis.
* **Media Storage**: AWS S3, Cloudflare R2, or Google Cloud Storage bucket for catalog images.
* **Health Monitoring**: Monitored via `/healthz` HTTP probe.

---

## 💡 Interview Defense Guide (30-Second Summary)

> *"DailyDrop is a full-stack quick-commerce application built with Flask and PostgreSQL. Rather than placing business logic inside route functions, I designed it with Flask Blueprints and a dedicated Service layer.*  
>  
> *The central engineering focus was **server-authoritative checkout and payment integrity**: cart prices are recalculated strictly against database records, inventory decrements happen atomically within a single transaction to prevent overselling, and payment webhooks use cryptographic HMAC validation with an order state machine. The application includes 61 automated Pytest tests, versioned database migrations, and health check observability endpoints."*

---

## 📄 License
This project is open-source under the [MIT License](LICENSE).
