# DailyDrop 🛒 — Online Grocery & Daily Essentials Store

DailyDrop is a full-stack e-commerce web application for ordering groceries and daily essentials with fast delivery. Built using Python, Flask, and PostgreSQL, the platform provides a smooth shopping experience with a responsive storefront, interactive cart and wishlist, live product search, secure checkout, and a full-featured admin management panel.

🔗 **[Live Demo](https://dailydrop17.vercel.app/)** | 📦 **[GitHub Repository](https://github.com/Spidey173/Dailydrop)**

---

## 🌟 Key Features

### 🛍️ Customer Storefront
- **Categorized Products**: 240+ grocery items organized across 10 categories (Fruits & Vegetables, Dairy, Snacks, Beverages, Household, Personal Care, Baby Care, etc.).
- **Instant Search**: Live search autocomplete dropdown to quickly find and add items to cart.
- **Cart & Wishlist**: Persistent cart and 1-click wishlist toggle saved across your session.
- **Product Details & Nutrition**: Interactive modal dialogs with nutritional insights and quality ratings.
- **Checkout & Payment**: Supports both Cash on Delivery (COD) and online payments via Razorpay.

### 🛡️ Admin Dashboard (`/admin_login`)
- **Store Telemetry**: Real-time summary of sales revenue, total orders, and registered customers.
- **Inventory Management**: Easy tools to update product stock, modify pricing, and maintain catalog items.
- **Order Tracking**: Manage customer order statuses from `Processing` to `Delivered`.

---

## 🛠️ Tech Stack

- **Backend**: Python 3.10+, Flask (Blueprints & Service Architecture)
- **Database**: PostgreSQL (Neon Serverless) / SQLite (for fast local tests)
- **Caching & Performance**: Redis for fast catalog access and stock synchronization
- **Frontend**: HTML5, Modern CSS3, JavaScript (ES6+), Bootstrap 5
- **Payment**: Razorpay Payment Gateway integration
- **CI / CD**: GitHub Actions automated testing suite
- **Deployment**: Vercel

---

## 📁 Project Structure

```
Daily-Drop/
├── app.py                  # Main application factory
├── database.py             # Database connection and queries
├── config.py               # Environment configuration
├── blueprints/             # Route handlers
│   ├── auth.py             # User login and registration
│   ├── cart.py             # Cart and checkout handling
│   ├── products.py         # Product catalog and search
│   └── admin.py            # Admin dashboard and analytics
├── services/               # Core business logic
│   ├── auth_service.py     # Authentication helpers
│   ├── order_service.py    # Order processing and inventory
│   ├── payment_service.py  # Razorpay integration
│   └── redis_service.py    # Redis caching and stock helper
├── static/                 # CSS stylesheets, JavaScript, and product images
├── templates/              # Jinja2 HTML templates
└── tests/                  # Automated pytest test suites
```

---

## 🚀 Getting Started

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
Create a `.env` file in the root directory (refer to `.env.example`):
```ini
FLASK_ENV=development
SECRET_KEY=your-secret-key-here
DATABASE_URL=your-neon-postgres-url
```

### 5. Run the Application
```bash
python app.py
```
Open [http://localhost:5000](http://localhost:5000) in your browser.

---

## 🔑 Demo Login Accounts

You can test the platform using the following pre-configured demo credentials:

| Role | Email | Password | Access URL |
| :--- | :--- | :--- | :--- |
| **Customer** | `demo_dailydrop@gmail.com` | `Demouser@123` | [`/login`](http://localhost:5000/login) |
| **Admin** | `admin_dailydrop@gmail.com` | `Dailydrop@173` | [`/admin_login`](http://localhost:5000/admin_login) |

---

## 🧪 Running Tests

The project includes an automated test suite verifying user authentication, catalog browsing, cart operations, and payments:

```bash
pytest -v
```

All tests run automatically on every push via GitHub Actions.

---

## 📄 License
This project is open-source under the [MIT License](LICENSE).
