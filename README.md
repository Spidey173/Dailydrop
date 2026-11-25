# DailyDrop 🛒 — Full-Stack Quick-Commerce Web Application

[![CI Pipeline](https://github.com/Spidey173/Dailydrop/actions/workflows/ci.yml/badge.svg)](https://github.com/Spidey173/Dailydrop/actions)
[![Tests](https://img.shields.io/badge/Pytest-110%20Passed-brightgreen?style=flat-square&logo=pytest)](tests/)
[![Backend](https://img.shields.io/badge/Python%203.11-Flask%203-blue?style=flat-square&logo=python)](app.py)
[![Database](https://img.shields.io/badge/PostgreSQL-16-336791?style=flat-square&logo=postgresql&logoColor=white)](database.py)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=flat-square&logo=docker&logoColor=white)](docker-compose.yml)
[![License](https://img.shields.io/badge/License-MIT-lightgrey?style=flat-square)](LICENSE)

**DailyDrop** is a full-stack quick-commerce web application built with Python, Flask, and PostgreSQL. It simulates a 10-minute grocery and daily-essentials delivery platform featuring a customer storefront, Razorpay checkout, inventory management, and an admin analytics dashboard.

🔗 **[Live Storefront](https://dailydrop18.vercel.app/)** · 🛡️ **[Admin Portal](https://dailydrop18.vercel.app/admin_login)** · 📊 **[Analytics Dashboard](https://dailydrop16.vercel.app/)** · 🩺 **[Health Check](https://dailydrop18.vercel.app/healthz)** · 📦 **[GitHub Repository](https://github.com/Spidey173/Dailydrop)**

---

## ✨ Features

- **User Authentication:** Secure registration, login, and session management for customers and admins.
- **Product Browsing & Categories:** Browse 241 seeded grocery items with category filtering and search.
- **Shopping Cart & Pricing:** Add/update items with server-side price calculation and delivery fee rules.
- **Order Placement & Tracking:** End-to-end checkout flow with order history and status progression.
- **Payment Integration:** Razorpay checkout with server-side signature verification and demo payment support.
- **Admin Dashboard & Inventory:** Manage catalog stock, track orders, and monitor delivery SLA metrics.
- **Business Analytics:** Built-in RFM customer segmentation, cohort retention, ABC inventory analysis, and market basket insights.

---

## 🛠️ Tech Stack

- **Backend:** Python 3.11, Flask 3, Gunicorn
- **Database & Cache:** PostgreSQL 16 (Neon / Docker), Redis (with in-memory fallback)
- **Frontend:** Jinja2 Templates, HTML5, CSS3, Vanilla JavaScript, Chart.js
- **Payments & Background Jobs:** Razorpay API, RQ (Redis Queue)
- **DevOps & Testing:** Docker, Docker Compose, Vercel, GitHub Actions, Pytest, Testcontainers

---

## 📸 Screenshots

> _To add screenshots: place image files in `static/screenshots/` (e.g., `storefront.png`, `admin-dashboard.png`) and update the image paths below._

| Storefront & Catalog | Admin Analytics Dashboard |
| :---: | :---: |
| `![Storefront](static/screenshots/storefront.png)` | `![Admin Dashboard](static/screenshots/admin-dashboard.png)` |

---

## 🏗️ Architecture Overview

DailyDrop follows a layered Flask architecture to keep routes, business logic, and database queries cleanly separated:

- **Blueprints (`blueprints/`):** Handle HTTP routes for auth, products, cart, storefront, and admin views.
- **Services (`services/`):** Encapsulate core business logic including order processing, pricing validation, stock reservation, and Razorpay verification.
- **Repositories (`repositories/`):** Manage PostgreSQL queries for users, products, orders, and analytics.
- **Cache & Worker (`redis_service.py`, `worker.py`):** Use Redis for caching and RQ for asynchronous background tasks.

---

## 🚀 Getting Started

### Option 1: Docker Compose (Recommended)
```bash
git clone https://github.com/Spidey173/Dailydrop.git
cd Dailydrop
cp .env.example .env
docker-compose up --build
```
- Storefront: `http://localhost:5000`
- Health Check: `http://localhost:5000/healthz`

### Option 2: Local Python Setup
```bash
git clone https://github.com/Spidey173/Dailydrop.git
cd Dailydrop
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m migrations.runner
python seed.py
python app.py
```

### Running Tests
The project includes **110 automated Pytest tests** running against ephemeral PostgreSQL and Redis containers via `testcontainers` (requires Docker running):
```bash
pytest
```

---

## 🔑 Demo Credentials

| Role | Email | Password | Login Path |
| :--- | :--- | :--- | :--- |
| **Customer** | `demo_dailydrop@gmail.com` | `Demouser@123` | `/login` |
| **Admin** | `admin_dailydrop@gmail.com` | `Dailydrop@173` | `/admin_login` |

---

## 📁 Project Structure

```text
Dailydrop/
├── app.py              # Flask application factory & blueprint registration
├── blueprints/         # Route handlers (auth, products, cart, admin, main)
├── services/           # Business logic (orders, payments, inventory, Redis)
├── repositories/       # PostgreSQL data access & analytics queries
├── migrations/         # Versioned SQL schema migrations
├── seeds/              # Initial 241-item product catalog
├── static/ & templates/# Frontend assets & Jinja2 HTML templates
├── tests/              # 110 automated Pytest integration & unit tests
├── worker.py           # Background RQ worker
└── docker-compose.yml  # Multi-container local setup
```

---

## 📚 What I Learned

- Designing a layered Flask backend separating routes, services, and SQL repositories.
- Preventing stock overselling and handling server-side pricing validation in PostgreSQL transactions.
- Integrating Razorpay payments with webhook/signature verification.
- Writing integration tests against real PostgreSQL and Redis instances using Docker and Testcontainers.
- Containerizing a multi-service Python app with Docker Compose and deploying serverless Flask apps to Vercel.

---

## 🔮 Future Improvements

- Real-time delivery tracking updates using WebSockets or Server-Sent Events.
- Automated email/SMS order notifications.
- Role-based access control for dark-store managers.

---

## 📄 License

This project is open-source under the [MIT License](LICENSE).
