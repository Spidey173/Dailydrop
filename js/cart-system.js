/**
 * DailyDrop — Premium Core Frontend Client Script
 * Version: 2.1 | Centralized Theme & Cart System 2026
 */

// Centralized Cart State Management
function updateCartCount() {
  try {
    const cart = JSON.parse(localStorage.getItem('cart')) || [];
    const count = cart.reduce((total, item) => total + (Number(item.quantity) || 1), 0);
    const el = document.getElementById('cart-count');
    if (el) el.textContent = count;
  } catch (e) {
    console.error('Error updating cart count:', e);
  }
}

function addToCart(productName, productPrice, productImage) {
  try {
    let cart = JSON.parse(localStorage.getItem('cart')) || [];
    // Ensure existing cart format has numbers for quantities
    cart = cart.map(item => ({
      ...item,
      quantity: Number(item.quantity) || 1
    }));

    const existingItem = cart.find(item => item.name === productName);
    if (existingItem) {
      existingItem.quantity += 1;
    } else {
      cart.push({
        name: productName,
        price: Number(productPrice),
        image: productImage,
        quantity: 1
      });
    }

    localStorage.setItem('cart', JSON.stringify(cart));
    updateCartCount();
    showAlert(productName);

    // Dispatch custom event to notify local page listeners (like cart.html) if needed
    window.dispatchEvent(new CustomEvent('cartUpdated'));
  } catch (e) {
    console.error('Error adding to cart:', e);
  }
}

// Standardized Premium Added-To-Cart Feedback Alert
function showAlert(name) {
  // Clear any existing alerts first to prevent stacking issues
  const existingAlerts = document.querySelectorAll('.ds-cart-alert');
  existingAlerts.forEach(alert => alert.remove());

  const msg = document.createElement('div');
  msg.className = 'ds-cart-alert';
  msg.innerHTML = `<i class="fas fa-check-circle"></i> &nbsp;<strong>${name}</strong> added to cart!`;
  
  Object.assign(msg.style, {
    position: 'fixed',
    bottom: '24px',
    right: '24px',
    zIndex: 9999,
    background: 'var(--brand)',
    color: 'white',
    padding: '12px 20px',
    borderRadius: '12px',
    fontFamily: 'var(--font)',
    fontSize: '0.875rem',
    boxShadow: '0 8px 28px rgba(22, 163, 74, 0.4)',
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    animation: 'slideIn 0.3s ease',
    fontWeight: '500',
    maxWidth: '340px'
  });
  
  document.body.appendChild(msg);
  setTimeout(() => {
    msg.style.opacity = '0';
    msg.style.transition = 'opacity 0.3s ease';
    setTimeout(() => msg.remove(), 300);
  }, 3000);
}

// Scroll to top helper
function scrollToTop() {
  window.scrollTo({
    top: 0,
    behavior: 'smooth'
  });
}

// Centralized Initialization
document.addEventListener('DOMContentLoaded', () => {
  // 1. Initial cart badge update
  updateCartCount();

  // 2. Scroll to Top button integration
  const scrollButton = document.querySelector('.scroll-to-top');
  if (scrollButton) {
    window.addEventListener('scroll', () => {
      if (window.pageYOffset > 300) {
        scrollButton.classList.add('show');
      } else {
        scrollButton.classList.remove('show');
      }
    });
    scrollButton.addEventListener('click', scrollToTop);
  }

  // 3. Theme Toggle Pill functionality
  const toggleBtn = document.getElementById('theme-toggle');
  if (toggleBtn) {
    toggleBtn.addEventListener('click', () => {
      const currentTheme = document.documentElement.getAttribute('data-theme') || 'light';
      const newTheme = currentTheme === 'light' ? 'dark' : 'light';
      document.documentElement.setAttribute('data-theme', newTheme);
      localStorage.setItem('theme', newTheme);
    });
  }
});

// Real-time synchronization across parallel browser tabs
window.addEventListener('storage', (e) => {
  if (e.key === 'cart') {
    updateCartCount();
    window.dispatchEvent(new CustomEvent('cartUpdated'));
  }
  if (e.key === 'theme') {
    document.documentElement.setAttribute('data-theme', e.newValue);
  }
});
