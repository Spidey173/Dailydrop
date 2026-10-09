# DailyDrop 🛒 — Full-Stack Grocery Delivery Web Application

DailyDrop is a full-stack e-commerce web application built with Python (Flask) and PostgreSQL for ordering groceries and daily essentials. It provides an end-to-end shopping workflow—from product discovery and cart management to checkout and order tracking—paired with an administrative panel for catalog management.

🔗 **[Live Demo](https://dailydrop17.vercel.app/)** | 📦 **[GitHub Repository](https://github.com/Spidey173/Dailydrop)**

---

## 🌟 What the Application Does

### 🛍️ Customer Storefront
- **Product Catalog**: Over 200+ daily grocery items organized into 10 practical categories (Fruits & Vegetables, Dairy & Breakfast, Snacks, Beverages, Household, etc.).
- **Live Search & Autocomplete**: Client-side instant search to filter and view items on the fly without repeated page reloads.
- **Cart & Wishlist**: Interactive cart management and wishlist persistence linked to user sessions.
- **Order Placement**: Seamless checkout supporting both Cash on Delivery (COD) and Razorpay test payments.
- **Order History**: Customers can view past orders with itemized breakdown and current delivery status.

### 🛡️ Admin Dashboard (`/admin_login`)
- **Store Overview**: Quick metrics summarizing total revenue, order count, and registered users.
- **Catalog & Stock Updates**: Admin controls to adjust item prices, update inventory quantities, or mark items as available/unavailable.
- **Order Processing**: Workflow to track and advance order statuses (`Processing` → `Shipped` → `Delivered`).

---

## 🛠️ Tech Stack & Architecture

- **Backend**: Python 3.10+, Flask
  - **Modular Blueprints**: Clean route separation across auth, products, cart, main, and admin modules.
  - **Service-Oriented Design**: Business logic isolated in dedicated services (`order_service.py`, `auth_service.py`, `product_service.py`).
- **Database**: PostgreSQL (hosted on Neon Serverless)
  - Connection pooling with `psycopg2` for efficient connection reuse.
  - SQLite support used during local automated testing.
- **Caching & Resilience**: Redis
  - Optional read-through caching for catalog data to reduce repetitive database queries.
  - Atomic stock check helper scripts to avoid overselling during simultaneous checkouts.
- **Frontend**: HTML5, Vanilla CSS3, JavaScript (ES6+), Bootstrap 5
- **Testing & CI/CD**:
  - `pytest` test suite covering core workflows (auth, checkout calculation, cart operations).
  - GitHub Actions workflow running automated test checks on push.
- **Deployment**: Vercel Serverless WSGI.

---

## 💡 What You Can Discuss in an Interview

When explaining this project in technical interviews, you can genuinely speak to:

1. **Structuring a Flask Monolith**:
   - Why you separated routes into Flask **Blueprints** and separated business rules into a **Service layer** rather than dumping SQL queries directly inside route functions.
2. **Database Transactions & Inventory Consistency**:
   - Handling stock decrementing at checkout inside a database transaction to prevent negative stock counts when multiple orders happen.
3. **Authentication & Session Security**:
   - Protecting passwords with secure `bcrypt` hashing, using session cookies for state, and applying role checks to keep customer routes separate from admin dashboard views.
4. **Resilient Architecture**:
   - Designing the application with graceful fallbacks: if Redis is not configured or goes down, the database queries still function normally without crashing the user's checkout.

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
├── services/               # Core business logic
│   ├── auth_service.py     # Password hashing & user validation
│   ├── order_service.py    # Order creation, items normalization, stock updates
│   ├── payment_service.py  # Razorpay order generation & signature verification
│   └── redis_service.py    # Optional cache helper & atomic stock decrements
├── static/                 # CSS stylesheets, UI icons, and product images
├── templates/              # Jinja2 HTML templates
└── tests/                  # Automated pytest test suites
```

---

## 🚀 Local Development Setup

### 1. Clone the Repository
```bash
git clone https://github.com/Spidey173/Dailydrop.git
cd Dailydrop
```

### 2. Create and Activate Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate
# On Windows: venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Create a `.env` file in the project root:
```ini
FLASK_ENV=development
SECRET_KEY=your-secret-key-here
DATABASE_URL=postgresql://user:password@host/dbname?sslmode=require
```
*(If `DATABASE_URL` is omitted, the test suite and local environment can run SQLite seamlessly).*

### 5. Run the Application
```bash
python app.py
```
Open [http://localhost:5000](http://localhost:5000) in your browser.

---

## 🔑 Demo Login Accounts

Pre-configured credentials available for testing:

| Role | Email | Password | Access URL |
| :--- | :--- | :--- | :--- |
| **Customer** | `demo_dailydrop@gmail.com` | `Demouser@123` | [`/login`](https://dailydrop17.vercel.app/login) |
| **Admin** | `admin_dailydrop@gmail.com` | `Dailydrop@173` | [`/admin_login`](https://dailydrop17.vercel.app/admin_login) |

---

## 🧪 Automated Testing

Run the test suite locally:
```bash
pytest -v
```

All tests execute automatically in GitHub Actions CI across Python matrix environments on code updates.

---

## 📄 License
This project is open-source under the [MIT License](LICENSE).
