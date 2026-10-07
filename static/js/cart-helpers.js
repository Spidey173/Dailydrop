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
      return;
  }
  const cart = JSON.parse(localStorage.getItem('cart')) || [];
  const count = cart.reduce((total, item) => total + (item.quantity || 1), 0);
  const cartCountEl = document.getElementById('cart-count');
  if (cartCountEl) {
      cartCountEl.textContent = count;
  }
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
  setTimeout(() => {
    notification.classList.remove('show');
  }, 2200);
}

// Automatically bind to DOM load
document.addEventListener('DOMContentLoaded', () => {
    updateCartCount();
    updateProductButtons();
});
