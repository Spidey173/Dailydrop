# DailyDrop 🛒 — Full-Stack Quick-Commerce Web Application

[![CI Pipeline](https://github.com/Spidey173/Dailydrop/actions/workflows/ci.yml/badge.svg)](https://github.com/Spidey173/Dailydrop/actions)
[![Tests](https://img.shields.io/badge/Pytest-107%20Passed-brightgreen?style=flat-square&logo=pytest)](tests/)
[![Backend](https://img.shields.io/badge/Backend-Python%203.11%20%7C%20Flask%203-blue?style=flat-square&logo=python)](app.py)
[![Database](https://img.shields.io/badge/Database-PostgreSQL%20(Neon%20%7C%20Docker)-336791?style=flat-square&logo=postgresql&logoColor=white)](database.py)
[![Cache](https://img.shields.io/badge/Cache-Redis%20(Fallback%20Safe)-DC382D?style=flat-square&logo=redis&logoColor=white)](services/redis_service.py)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=flat-square&logo=docker&logoColor=white)](docker-compose.yml)
[![License](https://img.shields.io/badge/License-MIT-lightgrey?style=flat-square)](LICENSE)

🔗 **[Live Storefront](https://dailydrop17.vercel.app/)** | 🛡️ **[Admin Portal](https://dailydrop17.vercel.app/admin_login)** | 🩺 **[Health Status](https://dailydrop17.vercel.app/healthz)** | 📦 **[GitHub Repository](https://github.com/Spidey173/Dailydrop)**

---

## ⚡ System Architecture

DailyDrop implements an enterprise-grade quick-commerce architecture designed to handle high-concurrency flash drops, prevent overselling, guarantee financial correctness, and isolate asynchronous background workers.

```mermaid
flowchart TD
    Client["Client Browser / Mobile Web"]

    subgraph Gateway["Ingress & Container Platform"]
        Gunicorn["Gunicorn WSGI Server (python:3.11-slim, gthread)"]
    end

    subgraph AppCore["Flask 3 Application Layer"]
        Blueprints["Blueprints (main, products, cart, auth, admin)"]
        Services["Domain Services (OrderService, PaymentService, AuthService)"]
        CatalogVal["CatalogValidationService (Server-Authoritative Pricing)"]
        InvSvc["InventoryReservationService (Two-Tier Decrement)"]
        OutboxSvc["OutboxService (Transactional Outbox)"]
        Repos["Domain Repositories (product, order, user, analytics)"]
    end

    subgraph FastTier["Tier 1: In-Memory / Distributed Cache"]
        Redis["Redis (Atomic Lua Stock Script, Idempotency Locks, Catalog L2)"]
    end

    subgraph Persistence["Tier 2: Relational ACID Persistence"]
        Postgres[("PostgreSQL 16 (Neon Serverless / Docker)")]
        Tables["products | orders | order_items | pending_orders | outbox_events"]
    end

    subgraph WorkerTier["Asynchronous Execution Tier"]
        RQ["RQ Worker (python worker.py)"]
        Tasks["Payment Capture, Notification Dispatch, Order Fulfillment"]
    end

    Client -->|HTTP / JSON| Gunicorn
    Gunicorn --> Blueprints
    Blueprints --> Services
    Services --> CatalogVal
    Services --> InvSvc
    Services --> OutboxSvc
    Services --> Repos
    InvSvc -->|Fast Reject Lua Check| Redis
    Repos -->|Connection Pool| Postgres
    OutboxSvc -->|Atomic Single Transaction Event Write| Postgres
    Redis -->|Job Queue| RQ
    RQ -->|Process Claimed Events| Postgres
```

---

## 💡 Key Design Decisions & Concurrency Guarantees

### 1. Two-Tier Inventory Reservation (Redis Fast Reject + PostgreSQL ACID Lock)
* **Tier 1 (Redis Lua)**: Under sudden traffic spikes, checkout requests first execute an atomic Lua script (`_LUA_DECREMENT_STOCK`) in Redis. If stock is insufficient, the request is rejected immediately at sub-millisecond latency (< 1ms) without burdening the relational database connection pool.
* **Tier 2 (PostgreSQL Conditional Row Update)**: During order creation inside an ACID transaction, stock is decremented using an atomic conditional update:
  ```sql
  UPDATE products SET stock = stock - %s WHERE product_id = %s AND stock >= %s
  ```
  If another transaction depleted stock in the microsecond window between Redis and PostgreSQL, `cursor.rowcount` is 0, causing immediate rollback and zero overselling.

### 2. Server-Authoritative Pricing & Strict Catalog Resolution
* **Anti-Tampering Guarantee**: Client payloads specifying cart prices, discounts, or delivery fees are completely ignored.
* **Exact Decimal Financial Arithmetic**: Subtotals and fees are calculated using Python's `Decimal` with standard `ROUND_HALF_UP` banking rules (`CurrencyService`), preventing IEEE-754 floating-point drift.
* **Strict Primary Key Resolution**: Products in cart must specify an explicit `product_id`. Fuzzy `ILIKE` name matching has been eliminated; unknown IDs return an immediate HTTP 400 rejection.
* **Deterministic Fee Boundary**: Orders $\ge$ ₹500 receive free delivery; orders < ₹500 incur a ₹30 delivery fee.

### 3. End-to-End Idempotency & State Machine Integrity
* **Idempotency Keys**: Mutating operations accept client-provided `Idempotency-Key` headers stored in Redis with atomic `SET NX EX`. Concurrent duplicate requests are rejected or served cached responses.
* **Database Unique Constraints**: `orders.payment_id` and `pending_orders.razorpay_order_id` enforce uniqueness at the storage engine level.
* **Payment FSM & Webhook Protection**: Orders advance linearly through states: `Created -> Paid -> Processing -> Packed -> Shipped -> Delivered`. Terminal states cannot regress; delayed or replayed Razorpay webhooks detect existing orders and exit cleanly without duplicate execution.

### 4. Transactional Outbox Pattern
* Order placement and domain event dispatch are coupled into **one atomic PostgreSQL transaction**.
* When an order is created, an event row is written to `outbox_events` in the same commit. If the database crashes or network fails, the event is guaranteed to persist alongside the order.
* The independent background worker (`worker.py` via RQ) claims pending events (`claimed_at`) and dispatches notifications, refunds, and analytics updates asynchronously.

---

## 🚀 Quickstart & Deployment Guide

### Option A: Run with Docker Compose (Recommended)
Spawns PostgreSQL, Redis, one-shot migration runner, Gunicorn web server, and the RQ worker:
```bash
# 1. Clone repository
git clone https://github.com/Spidey173/Dailydrop.git && cd Dailydrop

# 2. Copy environment template
cp .env.example .env

# 3. Build and launch all services
docker-compose up --build
```
* Storefront: [http://localhost:5000](http://localhost:5000)
* Health Check: [http://localhost:5000/healthz](http://localhost:5000/healthz)

### Option B: Local Virtual Environment
```bash
# 1. Setup virtual environment
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 2. Run versioned migrations & seed catalog
python -m migrations.runner
python seed.py

# 3. Start development server
python app.py
```

### Option C: Deploy to Vercel (Production Target)

DailyDrop is optimized for serverless production deployment on Vercel Serverless Functions (`@vercel/python` runtime) backed by Neon PostgreSQL and Upstash Redis. The live application is hosted at [https://dailydrop17.vercel.app/](https://dailydrop17.vercel.app/).

#### 1. Required Environment Variables on Vercel
Set the following environment variables in your Vercel Project Settings (`Settings -> Environment Variables`):

| Variable | Required | Description | Example / Recommended Value |
| :--- | :--- | :--- | :--- |
| `DATABASE_URL` | **Yes** | Neon PostgreSQL Pooled Connection URL | `postgresql://user:pass@ep-xyz-pooler.us-east-2.aws.neon.tech/neondb?sslmode=require` |
| `SECRET_KEY` | **Yes** | Strong, unique 32-byte hex key for sessions & CSRF | Generate: `python -c "import secrets; print(secrets.token_hex(32))"` |
| `FLASK_ENV` | **Yes** | Application environment | `production` |
| `REDIS_URL` | Optional | Upstash Redis connection string (`rediss://`) | `rediss://default:xxx@host.upstash.io:6379` (Graceful in-memory fallback if omitted) |
| `REDIS_ENABLED` | Optional | Enable or disable Redis integration | `true` |
| `RAZORPAY_KEY_ID` | Optional | Razorpay merchant API key ID | `rzp_live_...` or test key `rzp_test_...` |
| `RAZORPAY_KEY_SECRET` | Optional | Razorpay merchant secret | Keep confidential |
| `RAZORPAY_WEBHOOK_SECRET` | Optional | Razorpay webhook verification secret | For validating payment signatures |
| `DEMO_PAYMENTS` | Optional | Simulated payment bypass toggle | `false` (enforces server HMAC signature validation) |
| `DISABLE_FILE_UPLOADS` | Optional | Serverless read-only filesystem guard | Automatically set to `true` on Vercel |

#### 2. Run Database Migrations and Seed Catalog Before Deploy
Vercel serverless invocations are ephemeral and stateless; they do **not** run DDL migrations at request time. Run migrations and catalog seed from your local workstation pointing at your Neon database:

```bash
# 1. Apply all versioned migrations (idempotent; records in schema_migrations)
DATABASE_URL="postgresql://user:pass@ep-xyz.us-east-2.aws.neon.tech/neondb?sslmode=require" python -m migrations.runner

# 2. Seed initial catalog (241 items) and accounts (idempotent)
DATABASE_URL="postgresql://user:pass@ep-xyz.us-east-2.aws.neon.tech/neondb?sslmode=require" python seed.py
```

#### 3. Architecture Note: Outbox Execution on Vercel vs. Docker Compose
* **Vercel Serverless**: Ephemeral serverless functions do not host persistent worker daemons. When running on Vercel (`VERCEL=1`), transactional outbox tasks (such as order confirmation dispatch and inventory alert checks) execute **inline immediately after the database transaction commits** within the request lifecycle. Because these tasks are lightweight (< 50ms), execution remains well under Vercel's 10-second serverless execution ceiling.
* **Docker Compose / Persistent Hosting**: Executes a separate, dedicated `worker` container (`python worker.py`) running an RQ worker that continuously claims pending outbox events from PostgreSQL.

---

## 🗄️ Database Migrations

DailyDrop uses an idempotent, version-controlled migration runner that tracks applied versions in a `schema_migrations` audit table.

```bash
# Apply pending migrations
python -m migrations.runner

# Seed catalog products and demo accounts (idempotent)
python seed.py
```

* Migrations reside under `migrations/*.sql` and execute in strict alphabetical order.
* Executed automatically as a one-shot container in `docker-compose.yml` and before web startup in CI.

---

## 🧪 Testing Suite: Fast Offline Tests vs. Native PostgreSQL

The test suite contains **107 automated Pytests** covering unit logic, financial precision, domain repositories, payment FSM, and high-concurrency race protection.

### Fast Offline Unit Tests (In-Memory SQLite)
Runs 102 offline tests in ~2.5s using a thread-safe, in-memory SQLite wrapper in `conftest.py`:
```bash
pytest -m "not postgres" -v
```

### PostgreSQL Concurrency Tests
Runs the concurrency and atomic decrement tests against a real PostgreSQL instance:
```bash
# Ensure PostgreSQL is running on port 5432 and migrated
TEST_USE_REAL_POSTGRES=true DATABASE_URL="postgresql://test_user:test_password@localhost:5432/dailydrop_test" pytest -m "postgres" -v
```

### Run Entire Suite
```bash
pytest -v
```

---

## 🔑 Demo Access Credentials

| Role | Email | Password | Access URL |
| :--- | :--- | :--- | :--- |
| **Customer** | `demo_dailydrop@gmail.com` | `Demouser@123` | [`/login`](http://localhost:5000/login) |
| **Admin** | `admin_dailydrop@gmail.com` | `Dailydrop@173` | [`/admin_login`](http://localhost:5000/admin_login) |

> [!NOTE]
> `dev_tools/` contains local demo-data generators, never run in production.

---

## 📁 Repository Structure

```
DailyDrop/
├── app.py                      # Application factory (create_app), blueprints & health probes
├── config.py                   # Central environment configuration & validation
├── database.py                 # Threaded connection pool & transaction context manager
├── seed.py                     # Idempotent catalog & user seed script
├── worker.py                   # Background RQ worker for transactional outbox events
├── Dockerfile                  # Production container image (python:3.11-slim, non-root user)
├── docker-compose.yml          # Multi-container stack (web, worker, postgres, redis, migrate)
├── vercel.json                 # Vercel serverless production deployment configuration
├── pytest.ini                  # Pytest configuration and markers
├── blueprints/                 # Flask route controllers
│   ├── auth.py                 # Authentication & session management
│   ├── cart.py                 # Cart checkout, Razorpay payment & webhooks
│   ├── products.py             # Products catalog & GET /api/v1/products API
│   ├── admin.py                # Executive analytics & administrative controls
│   └── main.py                 # Core storefront views & health check
├── repositories/               # Decoupled domain data access repositories
│   ├── product_repository.py   # Catalog queries, tiered caching & stock updates
│   ├── order_repository.py     # Orders, order_items & pending_orders queries
│   ├── user_repository.py      # User authentication & caching
│   └── analytics_repository.py # Executive metrics, RFM segmentation & cohort analysis
├── services/                   # Single-responsibility business services
│   ├── order_service.py        # Order workflow orchestration & FSM transitions
│   ├── order_persistence_service.py # Deterministic single INSERT order persistence
│   ├── catalog_validation_service.py # Server-authoritative Decimal price validation
│   ├── inventory_reservation_service.py # Atomic stock reservation logic
│   ├── payment_service.py      # Razorpay payment verification & HMAC signatures
│   ├── idempotency_service.py  # Distributed idempotency tokens
│   ├── outbox_service.py       # Reliable transactional outbox dispatch
│   └── redis_service.py        # Redis client, Lua scripts & catalog caching
├── migrations/                 # Versioned SQL migrations & runner
│   ├── 001_initial_schema.sql
│   ├── ...
│   ├── 007_sync_missing_indexes_and_pending_orders_city.sql
│   └── runner.py               # CLI & container migration runner
├── seeds/                      # Canonical seed data
│   └── products.json           # 241 canonical grocery catalog items
├── dev_tools/                  # Local demo generators & simulation (excluded from prod)
│   └── traffic_simulator_service.py
├── static/                     # CSS, JS, images, and brand assets
│   ├── css/admin.css           # Modularized admin dashboard stylesheet
│   └── js/admin/               # Feature-split admin JS (tabs, charts, catalog, sqllab, etc.)
├── templates/                  # Jinja2 HTML templates
│   └── admin/partials/         # Admin dashboard modular Jinja partials
└── tests/                      # 107 automated Pytests
```

---

## 📄 License
This project is open-source under the [MIT License](LICENSE).
