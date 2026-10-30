# DailyDrop 🛒 — Full-Stack Quick-Commerce Web Application

[![CI Pipeline](https://github.com/Spidey173/Dailydrop/actions/workflows/ci.yml/badge.svg)](https://github.com/Spidey173/Dailydrop/actions)
[![Tests](https://img.shields.io/badge/Pytest-76%20Passed-brightgreen?style=flat-square&logo=pytest)](tests/)
[![Backend](https://img.shields.io/badge/Backend-Python%20%7C%20Flask-blue?style=flat-square&logo=python)](app.py)
[![Database](https://img.shields.io/badge/Database-PostgreSQL%20(Neon)-336791?style=flat-square&logo=postgresql&logoColor=white)](database.py)
[![Cache](https://img.shields.io/badge/Cache-Redis%20(Fallback%20Safe)-DC382D?style=flat-square&logo=redis&logoColor=white)](services/redis_service.py)
[![License](https://img.shields.io/badge/License-MIT-lightgrey?style=flat-square)](LICENSE)

🔗 **[Live Storefront](https://dailydrop17.vercel.app/)** | 🛡️ **[Admin Portal](https://dailydrop17.vercel.app/admin_login)** | 🩺 **[Health Status](https://dailydrop17.vercel.app/healthz)** | 📦 **[GitHub Repository](https://github.com/Spidey173/Dailydrop)**

---

## ⚡ At A Glance: Problem, Architecture, Proof & Scope

| Dimension | Specification |
| :--- | :--- |
| **Problem** | High-concurrency checkout spikes cause negative stock counts (overselling), while forged client cart payloads risk price and discount tampering. |
| **Architecture** | **Server-authoritative cart reconciliation**, atomic conditional SQL decrements inside ACID transactions, cryptographic Razorpay HMAC-SHA256 signature verification FSM, and adaptive Neon PostgreSQL connection pooling. |
| **Evidence & Benchmarks** | **76 automated Pytests** passing in CI across Python 3.10–3.12, sub-second search filtering across 200+ grocery SKUs, and zero overselling under multi-threaded concurrency simulation. |
| **Scope & Boundaries** | **Synthetic Data**: Seeded synthetic catalog of 200+ grocery SKUs across 10 categories; 3 PostgreSQL schemas (`core`, `auth_mgmt`, `audit_logs`). **Local Benchmark Environment**: Atomic conditional SQL decrements tested under simulated race conditions in local test harness. **Live Cloud Deployment**: Hosted on Vercel Serverless with cloud Neon PostgreSQL; simulated 10-minute order dispatch lifecycle. |
| **Verified Test Suite** | **76 / 76 Pytests passing** (unit, integration, concurrency, payment FSM, security). |

---

## 🏗️ Architecture Slice: Concurrency & Order Lifecycle

```text
┌─────────────────┐       ┌────────────────────────┐       ┌────────────────────────┐       ┌─────────────────┐
│   Client Cart   │ ────► │ Server Price Recompute │ ────► │ Atomic SQL Decrement   │ ────► │ Razorpay Auth   │ ────► Order Confirmed
│ (Items, Quant)  │       │ (DB Price Overwrite)   │       │ (WHERE stock >= qty)   │       │ (HMAC-SHA256)   │       (Simulated 10m Dispatch)
└─────────────────┘       └────────────────────────┘       └───────────┬────────────┘       └─────────────────┘
                                                                       │ (Insufficient Stock)
                                                                       ▼
                                                           [ Transaction Rollback ]
```

* **Guarantee**: Zero overselling under concurrent checkout spikes without row-level lock contention. If stock is insufficient, triggers immediate `conn.rollback()`.

---

## 🚀 Quickstart: Reproduce in 30 Seconds

```bash
# 1. Clone repository & setup virtual environment
git clone https://github.com/Spidey173/Dailydrop.git
cd Dailydrop
python3 -m venv venv && source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run verified test suite (76 automated Pytests)
pytest -v

# 4. Run local development server
python app.py
```
*Open [http://localhost:5000](http://localhost:5000) in your browser.*

---

## 🔑 Demo Access Accounts

| Role | Email | Password | Access URL |
| :--- | :--- | :--- | :--- |
| **Customer** | `demo_dailydrop@gmail.com` | `Demouser@123` | [`/login`](https://dailydrop17.vercel.app/login) |
| **Admin** | `admin_dailydrop@gmail.com` | `Dailydrop@173` | [`/admin_login`](https://dailydrop17.vercel.app/admin_login) |

> [!NOTE]
> **Sandbox Credentials**: Payments run in Razorpay Test Mode (`rzp_test_...`). No real money is charged.

---

## 🧪 Testing Architecture: Deterministic CI vs. Native PostgreSQL

The test suite covers authentication, cart calculations, forged price rejection, unknown product blocking, atomic checkout, stock race conditions, payment signature verification, webhook idempotency, and session security.

### Tier 1: Fast Deterministic CI Suite (76 Automated Pytests)
* Runs in **GitHub Actions CI** on `ubuntu-latest` against Python 3.10, 3.11, and 3.12.
* Uses an in-memory SQLite fixture (`_SHARED_SQLITE_CONN`) in `conftest.py` for hermetic, sub-2s execution without external network latency.
* Concurrency safety is verified via multi-threaded race simulation against conditional SQL updates (`UPDATE products SET stock = stock - %s WHERE product_id = %s AND stock >= %s`).

### Tier 2: Native PostgreSQL Row-Locking Verification
* Reviewers can verify native row locking (`FOR UPDATE` / `SKIP LOCKED`) against live PostgreSQL:
```bash
# Start local PostgreSQL container
docker run -d --name dailydrop-pg -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=dailydrop -p 5432:5432 postgres:16-alpine

# Run migrations
DATABASE_URL="postgresql://postgres:postgres@localhost:5432/dailydrop" python -m migrations.runner

# Run Pytest against live PostgreSQL
TEST_USE_REAL_POSTGRES=true DATABASE_URL="postgresql://postgres:postgres@localhost:5432/dailydrop" pytest tests/ -v
```

---

## 📚 Appendices & Deep Design Rationale

<details>
<summary><strong>1. Service-Oriented Layer Architecture</strong></summary>

Routes in Flask **Blueprints** (`auth`, `cart`, `products`, `admin`) delegate all business logic to dedicated domain services:
- `order_service.py`: Checkout orchestration, delivery progression, and order history.
- `catalog_validation_service.py`: Catalog resolution and authoritative price recomputation.
- `inventory_reservation_service.py`: Atomic stock decrement and reservation logic.
- `payment_service.py`: Razorpay order generation and HMAC-SHA256 signature verification.
- `idempotency_service.py`: Distributed Redis idempotency tokens and replay defense.
- `outbox_service.py`: Transactional outbox pattern for reliable event persistence.
- `auth_service.py`: Password hashing (Werkzeug Scrypt) and session management.
</details>

<details>
<summary><strong>2. Project Directory Tree</strong></summary>

```
Daily-Drop/
├── app.py                  # Application factory (create_app), health routes & security headers
├── extensions.py           # Extensions (CSRFProtect, Redis-backed distributed Limiter)
├── database.py             # Database connection pooling, SAVEPOINT isolation & schema execution
├── config.py               # Central environment configuration & fail-fast validation
├── worker.py               # Background transactional outbox worker (RQ with SimpleWorker)
├── Procfile                # Production process specification (web + worker)
├── blueprints/             # Route controllers (auth, cart, products, admin, main)
├── services/               # Single-responsibility domain services
├── migrations/             # Versioned SQL migrations & runner
├── static/                 # Stylesheets, UI icons, and product images
├── templates/              # Jinja2 HTML templates, error templates (404.html, 500.html)
└── tests/                  # 76 automated Pytest tests
```
</details>

<details>
<summary><strong>3. Defensive Security & Observability</strong></summary>

- **CSRF & Session Security**: Flask-WTF CSRF tokens validated on all mutating requests. Sessions regenerated on login/logout to prevent fixation.
- **Distributed Rate Limiting**: Flask-Limiter backed by Redis with thread-safe in-memory fallback.
- **Structured Sanitized Logging**: `SanitizingLogFormatter` scrubs passwords, API keys, webhook signatures, and payment details from logs.
- **Defensive Headers**: `X-Content-Type-Options: nosniff`, `X-Frame-Options: SAMEORIGIN`, and strict cookie flags (`HttpOnly`, `SameSite=Lax`).
- **Health Probes**: `/healthz` provides real-time diagnostics on database connectivity, query latency, and Redis status.
</details>

<details>
<summary><strong>4. Live Demo vs. Production Infrastructure Matrix</strong></summary>

| Capability | 🌐 Live Demo (`dailydrop17.vercel.app`) | 🚀 Full Production Setup |
| :--- | :--- | :--- |
| **Compute** | Vercel Serverless WSGI (Stateless) | Persistent Container PaaS (`gunicorn app:app -w 4 -k gthread`) |
| **Database** | Neon Cloud PostgreSQL (Serverless pooling) | Neon / AWS RDS PostgreSQL |
| **Pricing & Inventory** | Native server-authoritative recompute & atomic decrements | Native |
| **Payment Verification** | Native Razorpay HMAC-SHA256 & FSM | Live webhook listener with Redis idempotency |
| **Media Storage** | Base64 Data URLs in PostgreSQL (`products.image_path`) | Cloud Object Storage (AWS S3 / Cloudflare R2) with presigned URLs |
| **Background Tasks** | Synchronous inline execution fallback | Dedicated RQ background worker (`python worker.py`) |
</details>

---

## 📄 License
This project is open-source under the [MIT License](LICENSE).
