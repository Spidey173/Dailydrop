# 🛒 DailyDrop — Premium E-Commerce Frontend

DailyDrop is a premium, state-of-the-art grocery e-commerce frontend designed to deliver an exceptional, ultra-modern shopping experience. Styled with inspiration from leading tech startups like Vercel, Linear, and Stripe, DailyDrop features a high-fidelity glassmorphic design system, responsive layouts, a functional shopping cart, and a buttery-smooth dark/light mode engine.

👉 **Live Demo:** [https://dailydrop-iota.vercel.app](https://dailydrop-iota.vercel.app)

---

## ✨ Key Features

### 🌓 Premium Light & Dark Mode Engine
* **Bouncy Toggle Switch:** Sleek frosted-glass theme toggle pill featuring interactive Sun and Moon icons with a spring-bouncy CSS slider transition (`cubic-bezier(0.34, 1.56, 0.64, 1)`).
* **Zero-Flash Navigation:** A custom inline IIFE script placed at the top of every page reads user preferences directly from `localStorage` to completely prevent any white-flashes on page navigation or reload.
* **Tab Synchronization:** Changes to the theme in one browser tab instantly update all other open DailyDrop tabs in real-time.

### 🎨 World-Class Startup Visual Identity
* **High-End Glassmorphism:** Layered card components with custom translucent backdrops (`rgba(15, 23, 42, 0.72)` / `rgba(255, 255, 255, 0.85)`), inner borders, and high-fidelity box shadows.
* **SaaS Typography & Glows:** Title headers are powered by Inter with tightened letter-spacing (`-0.03em`) and custom glowing branding-emerald text shadows in Dark Mode.
* **Harmonious Palettes:** Off-white backgrounds in Light Mode paired with rich, premium slate charcoal tones in Dark Mode for absolute legibility and cinematic contrast.

### 📱 Seamless Responsiveness
* **Tailored Viewports:** Clean adaptive positioning across desktop, tablet, and mobile viewports.
* **Responsive Layout Shifts:** Clean margins, clamped fluid typography (`clamp()`), and auto-hiding secondary text details under `768px` to ensure zero layout crops or overflow issues on compact screens.

### ⚡ Client-Side Grocery Features
* Fully functional local client-side grocery database (`products-db.js`) supporting over 200 items across multiple categories.
* Interactive shopping cart, payment integration simulation, and persistent order tracking.

---

## 🛠️ Tech Stack & Structure

* **Frontend:** Semantic HTML5, Vanilla CSS3 (Custom Variables, Flexbox, CSS Grid)
* **Logic:** Vanilla ES6 JavaScript (LocalStorage APIs, window event handlers)
* **Typography:** Inter (via Google Fonts) & FontAwesome icons
* **Hosting:** Vercel Static Hosting with Clean URL redirection

---

## 📂 Project Structure

```bash
├── index.html             # Storefront Main Homepage
├── cart.html              # Interactive Shopping Cart
├── orders.html            # User Order History Page
├── payment.html           # Payment Simulation Checkout
├── intro.html             # Landing & Welcome Page
├── about_us.html          # Dynamic About Page
├── contact_us.html        # Interactive Contact Form
├── faqs.html              # Frequently Asked Questions
├── privacy.html           # Privacy Policy
├── terms.html             # Terms of Service
├── products-db.js         # JavaScript Client Database (200+ items)
├── design-system.css      # Core Global Typography & Styling Tokens
├── vercel.json            # Vercel Clean URL Routing Configuration
└── static/                # Static Asset Folders (Images, Icons, Logos)
```

---

## 🚀 Getting Started

### Local Setup
1. Clone the repository:
   ```bash
   git clone https://github.com/your-username/DailyDrop.git
   ```
2. Open the project folder:
   ```bash
   cd DailyDrop
   ```
3. Run the project locally. Since the site is built on vanilla HTML/CSS/JS, you can open `index.html` directly in your browser or run a simple local server:
   ```bash
   # Using python
   python -m http.server 8000
   
   # Using Node.js (serve)
   npx serve .
   ```
4. Access the store at `http://localhost:8000` or `http://localhost:3000`.

---

## ⚡ Deployment to Vercel

DailyDrop is optimized for one-click static hosting on **Vercel** with clean URL routing (strips `.html` from browser URLs):

1. Install the Vercel CLI (if not already installed):
   ```bash
   npm install -g vercel
   ```
2. Deploy directly from the project root:
   ```bash
   vercel --prod
   ```

---

## 📜 License
Distributed under the MIT License. See `LICENSE` for more information.
