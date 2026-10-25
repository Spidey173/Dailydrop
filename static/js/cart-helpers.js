// Global CSRF Token Retrieval Helper
function getCsrfToken() {
    return window.CSRF_TOKEN || document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
}

// Automatically attach X-CSRFToken to mutating same-origin fetch requests
if (typeof window !== 'undefined' && window.fetch) {
    const _origFetch = window.fetch;
    window.fetch = function(input, init) {
        init = init || {};
        const method = (init.method || 'GET').toUpperCase();
        if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(method)) {
            const token = getCsrfToken();
            if (token) {
                if (init.headers instanceof Headers) {
                    if (!init.headers.has('X-CSRFToken')) init.headers.append('X-CSRFToken', token);
                } else if (Array.isArray(init.headers)) {
                    init.headers.push(['X-CSRFToken', token]);
                } else {
                    init.headers = Object.assign({}, init.headers, { 'X-CSRFToken': token });
                }
            }
        }
        return _origFetch.call(this, input, init);
    };
}

// Check if user is logged in
function isUserLoggedIn() {
    if (typeof window.IS_USER_LOGGED_IN === 'boolean') {
        return window.IS_USER_LOGGED_IN;
    }
    // Check cookie
    if (document.cookie.split(';').some(item => item.trim() === 'is_logged_in=true' || item.trim().startsWith('is_logged_in=true'))) {
        return true;
    }
    // Check DOM elements rendered for authenticated session
    if (document.querySelector('a[href*="/logout"]') || document.querySelector('a[href*="logout"]') || document.querySelector('.welcome-text')) {
        return true;
    }
    return false;
}

function showGuestLoginAlert() {
    let notification = document.getElementById('cart-notification');
    if (!notification) {
      notification = document.createElement('div');
      notification.id = 'cart-notification';
      notification.className = 'notification';
      document.body.appendChild(notification);
    }
    notification.style.borderColor = '#ef4444';
    notification.innerHTML = `<i class="fas fa-lock" style="color: #ef4444;"></i> <span>Please <strong>Log In</strong> to use cart!</span>`;
    notification.classList.add('show');
    setTimeout(() => {
      window.location.href = "/login?next=" + encodeURIComponent(window.location.pathname);
    }, 1000);
}

let cart = JSON.parse(localStorage.getItem('cart')) || [];
if (cart.length > 0) {
  cart = cart.map(item => ({
    ...item,
    quantity: Number(item.quantity) || 1
  }));
  localStorage.setItem('cart', JSON.stringify(cart));
}


window.addEventListener('storage', () => {
  updateCartCount();
  updateProductButtons();
});

// Parabolic Fly-to-Cart Animation Engine
function animateFlyToCart(imgUrl, originEvtOrEl) {
    const cartTarget = document.querySelector('.cart-icon') || document.getElementById('cart-count');
    if (!cartTarget) return;

    const targetRect = cartTarget.getBoundingClientRect();
    const targetX = targetRect.left + targetRect.width / 2;
    const targetY = targetRect.top + targetRect.height / 2;

    let startX = window.innerWidth / 2;
    let startY = window.innerHeight / 2;

    if (originEvtOrEl instanceof HTMLElement) {
        const rect = originEvtOrEl.getBoundingClientRect();
        startX = rect.left + rect.width / 2;
        startY = rect.top + rect.height / 2;
    } else if (originEvtOrEl && originEvtOrEl.target) {
        const rect = originEvtOrEl.target.getBoundingClientRect();
        startX = rect.left + rect.width / 2;
        startY = rect.top + rect.height / 2;
    } else if (originEvtOrEl && typeof originEvtOrEl.clientX === 'number') {
        startX = originEvtOrEl.clientX;
        startY = originEvtOrEl.clientY;
    } else if (window.event && typeof window.event.clientX === 'number') {
        startX = window.event.clientX;
        startY = window.event.clientY;
    }

    // Create flying thumbnail clone
    const flyEl = document.createElement('div');
    flyEl.className = 'flying-cart-item';
    flyEl.innerHTML = `<img src="${imgUrl}" alt="Fly product" onerror="this.src='/static/logo.webp'" />`;
    
    flyEl.style.left = `${startX - 25}px`;
    flyEl.style.top = `${startY - 25}px`;
    document.body.appendChild(flyEl);

    // Parabolic Bezier Flight (700ms duration)
    const startTime = performance.now();
    const duration = 650;
    const arcControlY = Math.min(startY, targetY) - 120;

    function step(timestamp) {
        const elapsed = timestamp - startTime;
        const progress = Math.min(elapsed / duration, 1);

        const t = progress;
        const currentX = (1 - t) * (1 - t) * startX + 2 * (1 - t) * t * ((startX + targetX) / 2) + t * t * targetX;
        const currentY = (1 - t) * (1 - t) * startY + 2 * (1 - t) * t * arcControlY + t * t * targetY;

        const scale = 1.0 - progress * 0.72;
        const rotate = progress * 420;
        const opacity = progress > 0.88 ? (1 - progress) / 0.12 : 1;

        flyEl.style.left = `${currentX - 25}px`;
        flyEl.style.top = `${currentY - 25}px`;
        flyEl.style.transform = `scale(${scale}) rotate(${rotate}deg)`;
        flyEl.style.opacity = opacity;

        if (progress < 1) {
            requestAnimationFrame(step);
        } else {
            flyEl.remove();
            triggerCartBounce();
        }
    }

    requestAnimationFrame(step);
}

// Bounce Cart Icon and Pulse Numeric Badge
function triggerCartBounce() {
    const cartIcon = document.querySelector('.cart-icon');
    const cartCount = document.getElementById('cart-count');

    if (cartIcon) {
        cartIcon.classList.remove('bounce-cart');
        void cartIcon.offsetWidth; // Trigger reflow
        cartIcon.classList.add('bounce-cart');
    }

    if (cartCount) {
        cartCount.classList.remove('badge-pop');
        void cartCount.offsetWidth; // Trigger reflow
        cartCount.classList.add('badge-pop');
    }
}

function addToCart(productName, productPrice, productImage, evt) {
    if (!isUserLoggedIn()) {
        showGuestLoginAlert();
        return;
    }

    // Launch Parabolic Fly Animation
    animateFlyToCart(productImage, evt || window.event);

    let cart = JSON.parse(localStorage.getItem('cart')) || [];
    const existingItem = cart.find(item => item.name === productName);

    if (existingItem) {
        existingItem.quantity += 1;
    } else {
        cart.push({
            name: productName,
            price: productPrice,
            image: productImage,
            quantity: 1
        });
    }

    localStorage.setItem('cart', JSON.stringify(cart));
    updateCartCount();
    updateProductButtons();
    showAddedToCartAlert(productName);
}

function changeQuantity(productName, delta, price, img, event) {
    if (event) event.stopPropagation();
    if (!isUserLoggedIn()) {
        showGuestLoginAlert();
        return;
    }

    if (delta > 0) {
        animateFlyToCart(img, event || window.event);
    }

    let cart = JSON.parse(localStorage.getItem('cart')) || [];
    const existingItem = cart.find(item => item.name === productName);
    
    if (existingItem) {
        existingItem.quantity += delta;
        if (existingItem.quantity <= 0) {
            cart = cart.filter(item => item.name !== productName);
        }
    } else if (delta > 0) {
        cart.push({
            name: productName,
            price: price,
            image: img,
            quantity: 1
        });
    }
    
    localStorage.setItem('cart', JSON.stringify(cart));
    updateCartCount();
    updateProductButtons();
    
    // Dispatch event to sync other tabs or templates
    window.dispatchEvent(new Event('storage'));
}

function parseAddToCart(onclickStr) {
    if (!onclickStr) return null;
    const start = onclickStr.indexOf('addToCart(');
    if (start === -1) return null;
    const end = onclickStr.lastIndexOf(')');
    if (end === -1 || end < start) return null;
    const content = onclickStr.substring(start + 10, end);
    
    let args = [];
    let currentArg = '';
    let inQuote = false;
    let quoteChar = '';
    let escaped = false;
    
    for (let i = 0; i < content.length; i++) {
        const char = content[i];
        if (escaped) {
            currentArg += char;
            escaped = false;
        } else if (char === '\\') {
            escaped = true;
        } else if ((char === "'" || char === '"') && !inQuote) {
            inQuote = true;
            quoteChar = char;
        } else if (char === quoteChar && inQuote) {
            inQuote = false;
            quoteChar = '';
        } else if (char === ',' && !inQuote) {
            args.push(currentArg.trim());
            currentArg = '';
        } else {
            currentArg += char;
        }
    }
    args.push(currentArg.trim());
    
    if (args.length >= 3) {
        let name = args[0];
        if ((name.startsWith("'") && name.endsWith("'")) || (name.startsWith('"') && name.endsWith('"'))) {
            name = name.slice(1, -1);
        }
        name = name.replace(/\\'/g, "'").replace(/\\"/g, '"');
        
        let price = parseFloat(args[1]);
        
        let img = args[2];
        if ((img.startsWith("'") && img.endsWith("'")) || (img.startsWith('"') && img.endsWith('"'))) {
            img = img.slice(1, -1);
        }
        
        return { name, price, img };
    }
    return null;
}

function updateProductButtons() {
    const cart = JSON.parse(localStorage.getItem('cart')) || [];
    
    // Find all raw elements with onclick starting with or containing addToCart that aren't wrapped yet
    const addButtons = document.querySelectorAll('.add-to-cart-btn, [onclick^="addToCart"]');
    
    addButtons.forEach(btn => {
        if (btn.closest('.qty-adjuster-container')) {
            return;
        }
        
        const onclickStr = btn.getAttribute('onclick');
        if (!onclickStr) return;
        
        const parsed = parseAddToCart(onclickStr);
        if (!parsed) return;
        
        const { name, price, img } = parsed;
        const originalHtml = btn.innerHTML;
        const originalClass = btn.className;
        
        // Find or create parent container for quantity selector
        const container = document.createElement('div');
        container.className = 'qty-adjuster-container';
        container.setAttribute('data-product-name', name);
        container.setAttribute('data-product-price', price.toString());
        container.setAttribute('data-product-image', img);
        container.setAttribute('data-btn-html', originalHtml);
        container.setAttribute('data-btn-class', originalClass);
        
        btn.parentNode.insertBefore(container, btn);
        container.appendChild(btn);
    });
    
    // Now update all qty-adjuster-containers with the correct DOM based on the cart state
    const containers = document.querySelectorAll('.qty-adjuster-container');
    containers.forEach(container => {
        const name = container.getAttribute('data-product-name');
        const price = parseFloat(container.getAttribute('data-product-price'));
        const img = container.getAttribute('data-product-image');
        const btnHtml = container.getAttribute('data-btn-html') || 'ADD';
        const btnClass = container.getAttribute('data-btn-class') || 'add-to-cart-btn';
        
        const cartItem = cart.find(item => item.name === name);
        
        if (cartItem && cartItem.quantity > 0) {
            container.innerHTML = `
                <div class="qty-toggle">
                    <button class="qty-btn" onclick="changeQuantity('${name.replace(/'/g, "\\'")}', -1, ${price}, '${img}', event)">−</button>
                    <span class="qty-val">${cartItem.quantity}</span>
                    <button class="qty-btn" onclick="changeQuantity('${name.replace(/'/g, "\\'")}', 1, ${price}, '${img}', event)">+</button>
                </div>
            `;
        } else {
            container.innerHTML = `
                <button class="${btnClass}" onclick="addToCart('${name.replace(/'/g, "\\'")}', ${price}, '${img}', event)">${btnHtml}</button>
            `;
        }
    });
}

function updateCartCount() {
  if (!isUserLoggedIn()) {
      localStorage.removeItem('cart');
      const cartCountEl = document.getElementById('cart-count');
      if (cartCountEl) cartCountEl.textContent = '0';
      const mobileTopBadge = document.getElementById('mobile-top-cart-badge');
      if (mobileTopBadge) {
          mobileTopBadge.textContent = '0';
          mobileTopBadge.style.display = 'none';
      }
      const drawerCartBadge = document.getElementById('drawer-cart-badge');
      if (drawerCartBadge) {
          drawerCartBadge.textContent = '0';
          drawerCartBadge.style.display = 'none';
      }
      const mobileNavBadge = document.getElementById('mobile-nav-cart-badge');
      if (mobileNavBadge) {
          mobileNavBadge.textContent = '0';
          mobileNavBadge.style.display = 'none';
      }
      const floatingBar = document.getElementById('mobileFloatingCartBar');
      if (floatingBar) floatingBar.remove();
      return;
  }
  const cart = JSON.parse(localStorage.getItem('cart')) || [];
  const count = cart.reduce((total, item) => total + (item.quantity || 1), 0);
  const subtotal = cart.reduce((total, item) => total + ((Number(item.price) || 0) * (item.quantity || 1)), 0);

  // Desktop badge
  const cartCountEl = document.getElementById('cart-count');
  if (cartCountEl) {
      cartCountEl.textContent = count;
  }

  // Mobile Top Cart button badge
  const mobileTopBadge = document.getElementById('mobile-top-cart-badge');
  if (mobileTopBadge) {
      mobileTopBadge.textContent = count;
      mobileTopBadge.style.display = count > 0 ? 'flex' : 'none';
  }

  // Drawer Cart link badge
  const drawerCartBadge = document.getElementById('drawer-cart-badge');
  if (drawerCartBadge) {
      drawerCartBadge.textContent = count;
      drawerCartBadge.style.display = count > 0 ? 'inline-block' : 'none';
  }

  // Mobile Bottom Nav badge
  const mobileNavBadge = document.getElementById('mobile-nav-cart-badge');
  if (mobileNavBadge) {
      mobileNavBadge.textContent = count;
      mobileNavBadge.style.display = count > 0 ? 'flex' : 'none';
  }

  // Sync mobile wishlist badges if available
  const desktopWishlist = document.getElementById('wishlist-count');
  const mobileWishlist = document.getElementById('mobile-nav-wishlist-badge');
  const drawerWishlist = document.getElementById('drawer-wishlist-badge');
  if (desktopWishlist) {
      const wCount = parseInt(desktopWishlist.textContent) || 0;
      if (mobileWishlist) {
          mobileWishlist.textContent = wCount;
          mobileWishlist.style.display = wCount > 0 ? 'flex' : 'none';
      }
      if (drawerWishlist) {
          drawerWishlist.textContent = wCount;
          drawerWishlist.style.display = wCount > 0 ? 'inline-block' : 'none';
      }
  }

  // Blinkit Floating Mini-Cart Bar
  updateMobileFloatingCart(count, subtotal);
}

function updateMobileFloatingCart(count, subtotal) {
  const currentPath = window.location.pathname;
  // Don't show floating cart on cart, payment, or admin pages
  if (currentPath.includes('/cart') || currentPath.includes('/payment') || currentPath.includes('/admin')) {
      const existing = document.getElementById('mobileFloatingCartBar');
      if (existing) existing.remove();
      return;
  }

  let floatingBar = document.getElementById('mobileFloatingCartBar');
  if (count <= 0) {
      if (floatingBar) floatingBar.remove();
      return;
  }

  if (!floatingBar) {
      floatingBar = document.createElement('a');
      floatingBar.id = 'mobileFloatingCartBar';
      floatingBar.className = 'mobile-floating-cart-bar';
      floatingBar.href = '/cart';
      document.body.appendChild(floatingBar);
  }

  floatingBar.innerHTML = `
      <div class="floating-cart-info">
          <div class="floating-cart-icon-wrap">
              <i class="fas fa-shopping-basket"></i>
          </div>
          <div class="floating-cart-text">
              <span class="floating-cart-count">${count} Item${count > 1 ? 's' : ''} Added</span>
              <span class="floating-cart-subtotal">Rs. ${subtotal.toFixed(2)}</span>
          </div>
      </div>
      <div class="floating-cart-action">
          View Cart <i class="fas fa-arrow-right"></i>
      </div>
  `;
}

function initMobileExperience() {
  const currentPath = window.location.pathname;
  if (currentPath.includes('/admin')) return;

  const isHome = currentPath === '/' || currentPath.includes('/intro');
  const isCategory = ['/categories', '/category', '/vegetables', '/dairy_breakfast', '/snacks', '/baby_care', '/personal_care', '/household_items', '/home_kitchen', '/grocery', '/beverages', '/frozen_foods'].some(p => currentPath.includes(p));
  const isWishlist = currentPath.includes('/wishlist');
  const isOrders = currentPath.includes('/orders');
  const isCart = currentPath.includes('/cart');
  const isAbout = currentPath.includes('/about');
  const isContact = currentPath.includes('/contact');
  const isFaqs = currentPath.includes('/faqs');
  const loggedIn = isUserLoggedIn();

  // 1. Render Mobile Top Header Controls ("Three -" Hamburger Menu) inside .navbar-container
  const navbarContainer = document.querySelector('.navbar-container');
  if (navbarContainer && !document.getElementById('mobileHeaderControls')) {
      const controls = document.createElement('div');
      controls.className = 'mobile-header-controls';
      controls.id = 'mobileHeaderControls';
      controls.innerHTML = `
          <button class="mobile-hamburger-btn" id="mobileHamburgerBtn" aria-label="Open navigation menu" type="button">
              <span class="bar"></span>
              <span class="bar"></span>
              <span class="bar"></span>
          </button>
      `;
      navbarContainer.appendChild(controls);
  }

  // 2. Render Mobile Bottom Navigation Bar if not already present
  if (!document.getElementById('mobileBottomNav')) {
      const bottomNav = document.createElement('nav');
      bottomNav.id = 'mobileBottomNav';
      bottomNav.className = 'mobile-bottom-nav';
      bottomNav.setAttribute('aria-label', 'Mobile Bottom Navigation');

      bottomNav.innerHTML = `
          <a href="/" class="mobile-nav-item ${isHome ? 'active' : ''}" title="Home">
              <i class="fas fa-house"></i>
              <span>Home</span>
          </a>
          <a href="/categories" class="mobile-nav-item ${isCategory ? 'active' : ''}" title="Categories">
              <i class="fas fa-border-all"></i>
              <span>Categories</span>
          </a>
          <a href="/wishlist" class="mobile-nav-item ${isWishlist ? 'active' : ''}" title="Wishlist">
              <i class="fas fa-heart"></i>
              <span>Wishlist</span>
              <span class="mobile-nav-badge" id="mobile-nav-wishlist-badge" style="display:none;">0</span>
          </a>
          <a href="/orders" class="mobile-nav-item ${isOrders ? 'active' : ''}" title="My Orders">
              <i class="fas fa-box"></i>
              <span>Orders</span>
          </a>
          <a href="/cart" class="mobile-nav-item ${isCart ? 'active' : ''}" title="My Cart">
              <i class="fas fa-shopping-cart"></i>
              <span>Cart</span>
              <span class="mobile-nav-badge" id="mobile-nav-cart-badge" style="display:none;">0</span>
          </a>
      `;
      document.body.appendChild(bottomNav);
  }

  // 3. Render Mobile Slide-Out Drawer (The "Three -" Hamburger Menu Drawer)
  if (!document.getElementById('mobileDrawerNav')) {
      const backdrop = document.createElement('div');
      backdrop.className = 'mobile-drawer-backdrop';
      backdrop.id = 'mobileDrawerBackdrop';
      document.body.appendChild(backdrop);

      const drawer = document.createElement('aside');
      drawer.className = 'mobile-drawer-nav';
      drawer.id = 'mobileDrawerNav';
      drawer.setAttribute('aria-label', 'Mobile Navigation Drawer');

      drawer.innerHTML = `
          <div class="drawer-header">
              <a href="/" class="logo">
                  <i class="fas fa-shopping-basket"></i> Daily<span>Drop</span>
              </a>
              <button class="drawer-close-btn" id="drawerCloseBtn" aria-label="Close navigation menu" type="button">
                  <i class="fas fa-times"></i>
              </button>
          </div>
          <div class="drawer-user-info">
              <div class="drawer-avatar">
                  <i class="fas ${loggedIn ? 'fa-user-check' : 'fa-user'}"></i>
              </div>
              <div class="drawer-user-details">
                  <h5>${loggedIn ? 'Welcome Back!' : 'Welcome to DailyDrop'}</h5>
                  <p>${loggedIn ? 'Simulated Quick Delivery' : 'Log in for orders & wishlist'}</p>
              </div>
          </div>
          <div class="drawer-links-group">
              <a href="/orders" class="drawer-link ${isOrders ? 'active' : ''}">
                  <div class="drawer-link-content">
                      <i class="fas fa-box"></i>
                      <span>My Orders</span>
                  </div>
                  <i class="fas fa-chevron-right" style="font-size: 0.75rem; opacity: 0.5;"></i>
              </a>
              <a href="/wishlist" class="drawer-link ${isWishlist ? 'active' : ''}">
                  <div class="drawer-link-content">
                      <i class="fas fa-heart"></i>
                      <span>Wishlist</span>
                  </div>
                  <span class="drawer-badge" id="drawer-wishlist-badge" style="display: none;">0</span>
              </a>
              <a href="/cart" class="drawer-link ${isCart ? 'active' : ''}">
                  <div class="drawer-link-content">
                      <i class="fas fa-shopping-cart"></i>
                      <span>My Cart</span>
                  </div>
                  <span class="drawer-badge" id="drawer-cart-badge" style="display: none;">0</span>
              </a>
          </div>
          <div class="drawer-divider"></div>
          <div class="drawer-links-group">
              <a href="/about-us" class="drawer-link ${isAbout ? 'active' : ''}">
                  <div class="drawer-link-content">
                      <i class="fas fa-info-circle"></i>
                      <span>About Us</span>
                  </div>
              </a>
              <a href="/contact-us" class="drawer-link ${isContact ? 'active' : ''}">
                  <div class="drawer-link-content">
                      <i class="fas fa-envelope"></i>
                      <span>Contact Us</span>
                  </div>
              </a>
              <a href="/faqs" class="drawer-link ${isFaqs ? 'active' : ''}">
                  <div class="drawer-link-content">
                      <i class="fas fa-question-circle"></i>
                      <span>FAQs & Help</span>
                  </div>
              </a>
          </div>
          ${loggedIn ? `
              <a href="/logout" class="drawer-auth-btn logout">
                  <i class="fas fa-sign-out-alt"></i> Logout
              </a>
          ` : `
              <a href="/login" class="drawer-auth-btn login">
                  <i class="fas fa-sign-in-alt"></i> Login / Sign Up
              </a>
          `}
      `;
      document.body.appendChild(drawer);
  }

  // Always bind drawer event listeners (works for both SSR and dynamically rendered drawer)
  const drawer = document.getElementById('mobileDrawerNav');
  const backdrop = document.getElementById('mobileDrawerBackdrop');
  const hamburgerBtn = document.getElementById('mobileHamburgerBtn');
  const drawerCloseBtn = document.getElementById('drawerCloseBtn');

  const openDrawer = () => {
      drawer?.classList.add('show');
      backdrop?.classList.add('show');
      document.body.style.overflow = 'hidden';
  };

  const closeDrawer = () => {
      drawer?.classList.remove('show');
      backdrop?.classList.remove('show');
      document.body.style.overflow = '';
  };

  if (hamburgerBtn && !hamburgerBtn.dataset.bound) {
      hamburgerBtn.dataset.bound = 'true';
      hamburgerBtn.addEventListener('click', (e) => {
          e.preventDefault();
          e.stopPropagation();
          openDrawer();
      });
  }

  if (drawerCloseBtn && !drawerCloseBtn.dataset.bound) {
      drawerCloseBtn.dataset.bound = 'true';
      drawerCloseBtn.addEventListener('click', (e) => {
          e.preventDefault();
          e.stopPropagation();
          closeDrawer();
      });
  }

  if (backdrop && !backdrop.dataset.bound) {
      backdrop.dataset.bound = 'true';
      backdrop.addEventListener('click', closeDrawer);
  }

  if (!window._drawerEscapeBound) {
      window._drawerEscapeBound = true;
      document.addEventListener('keydown', (e) => {
          if (e.key === 'Escape' && drawer?.classList.contains('show')) {
              closeDrawer();
          }
      });
  }

  drawer?.querySelectorAll('.drawer-link').forEach(link => {
      if (!link.dataset.bound) {
          link.dataset.bound = 'true';
          link.addEventListener('click', () => {
              closeDrawer();
          });
      }
  });

  if (typeof window.initLiveSearch === 'function') {
      window.initLiveSearch();
  }

  updateCartCount();
}

function showAddedToCartAlert(productName) {
  let notification = document.getElementById('cart-notification');
  if (!notification) {
    notification = document.createElement('div');
    notification.id = 'cart-notification';
    notification.className = 'notification';
    document.body.appendChild(notification);
  }
  notification.innerHTML = `<i class="fas fa-check-circle me-1" style="color:#34D399;"></i> <span><strong>${productName}</strong> added to cart!</span>`;
  notification.classList.add('show');
  if (navigator.vibrate) {
    try { navigator.vibrate(30); } catch(e) {}
  }
  setTimeout(() => {
    notification.classList.remove('show');
  }, 2200);
}

// Automatically bind to DOM load
document.addEventListener('DOMContentLoaded', () => {
    initMobileExperience();
    updateCartCount();
    updateProductButtons();
});

// Re-evaluate on resize/orientation change
window.addEventListener('resize', () => {
    updateCartCount();
});

// Global modal backdrop lockup prevention:
// Ensures that after any modal action or navigation, stale backdrops never freeze the user interface
document.addEventListener('hidden.bs.modal', function () {
    document.querySelectorAll('.modal-backdrop').forEach(el => el.remove());
    document.body.classList.remove('modal-open');
    document.body.style.removeProperty('overflow');
    document.body.style.removeProperty('padding-right');
});
