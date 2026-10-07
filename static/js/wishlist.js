/**
 * Daily Drop - Wishlist State Manager & Interactive Component
 */

window.wishlistProductIds = new Set();

// Fetch wishlisted product IDs on initialization
async function initWishlist() {
  try {
    const res = await fetch('/api/v1/wishlist/ids');
    if (!res.ok) return;
    const data = await res.json();
    if (data.success && Array.isArray(data.ids)) {
      window.wishlistProductIds = new Set(data.ids.map(Number));
      updateWishlistNavbarBadge(data.count || window.wishlistProductIds.size);
      updateWishlistHeartButtons();
    }
  } catch (err) {
    console.debug('Could not load wishlist IDs:', err);
  }
}

// Check if a product is in wishlist
function isInWishlist(productId) {
  return window.wishlistProductIds.has(Number(productId));
}

// Update navbar badge count
function updateWishlistNavbarBadge(count) {
  const badge = document.getElementById('wishlist-count');
  if (badge) {
    badge.textContent = count;
    badge.classList.remove('badge-pop');
    void badge.offsetWidth; // Trigger reflow
    badge.classList.add('badge-pop');
  }
}

// Update all heart buttons on the page
function updateWishlistHeartButtons() {
  document.querySelectorAll('.wishlist-heart-btn').forEach(btn => {
    const pid = Number(btn.getAttribute('data-product-id'));
    if (!pid) return;
    const isSaved = window.wishlistProductIds.has(pid);
    btn.classList.toggle('active', isSaved);
    const icon = btn.querySelector('i');
    if (icon) {
      icon.className = isSaved ? 'fas fa-heart' : 'far fa-heart';
    }
  });
}

// Toggle wishlist item
async function toggleWishlist(productId, evtOrEl) {
  if (evtOrEl && typeof evtOrEl.stopPropagation === 'function') {
    evtOrEl.stopPropagation();
    evtOrEl.preventDefault();
  }

  // Check login
  if (typeof isUserLoggedIn === 'function' && !isUserLoggedIn()) {
    if (typeof showGuestLoginAlert === 'function') {
      showGuestLoginAlert();
    } else {
      window.location.href = '/login?next=' + encodeURIComponent(window.location.pathname);
    }
    return;
  }

  const pid = Number(productId);
  if (!pid) return;

  // Optimistic UI toggle
  const isCurrentlySaved = window.wishlistProductIds.has(pid);
  if (isCurrentlySaved) {
    window.wishlistProductIds.delete(pid);
  } else {
    window.wishlistProductIds.add(pid);
  }
  updateWishlistHeartButtons();
  updateWishlistNavbarBadge(window.wishlistProductIds.size);

  try {
    const response = await fetch('/api/v1/wishlist/toggle', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ product_id: pid })
    });

    const data = await response.json();
    if (data.success) {
      if (data.in_wishlist) {
        window.wishlistProductIds.add(pid);
      } else {
        window.wishlistProductIds.delete(pid);
      }
      updateWishlistNavbarBadge(data.count !== undefined ? data.count : window.wishlistProductIds.size);
      updateWishlistHeartButtons();
      showWishlistToast(data.message || (data.in_wishlist ? 'Saved to Wishlist' : 'Removed from Wishlist'), data.in_wishlist);
    } else {
      // Revert on error
      if (isCurrentlySaved) window.wishlistProductIds.add(pid);
      else window.wishlistProductIds.delete(pid);
      updateWishlistHeartButtons();
      updateWishlistNavbarBadge(window.wishlistProductIds.size);
      showWishlistToast(data.message || 'Error updating wishlist', false);
    }
  } catch (err) {
    console.error('Wishlist toggle error:', err);
    // Revert
    if (isCurrentlySaved) window.wishlistProductIds.add(pid);
    else window.wishlistProductIds.delete(pid);
    updateWishlistHeartButtons();
    updateWishlistNavbarBadge(window.wishlistProductIds.size);
  }
}

// Remove from dedicated wishlist page
async function removeFromWishlistPage(productId, buttonEl) {
  const pid = Number(productId);
  if (!pid) return;

  const card = buttonEl.closest('.product-card') || buttonEl.closest('.wishlist-item-card');
  if (card) {
    card.style.transition = 'all 0.35s ease';
    card.style.opacity = '0.4';
    card.style.transform = 'scale(0.95)';
  }

  try {
    const res = await fetch('/api/v1/wishlist/remove', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ product_id: pid })
    });
    const data = await res.json();
    if (data.success) {
      window.wishlistProductIds.delete(pid);
      updateWishlistNavbarBadge(data.count !== undefined ? data.count : window.wishlistProductIds.size);
      
      if (card) {
        card.style.opacity = '0';
        card.style.transform = 'scale(0.8)';
        setTimeout(() => {
          card.remove();
          const grid = document.getElementById('wishlistGrid');
          if (grid && grid.querySelectorAll('.product-card, .wishlist-item-card').length === 0) {
            const emptyEl = document.getElementById('wishlistEmptyState');
            if (emptyEl) emptyEl.style.display = 'block';
            if (grid) grid.style.display = 'none';
          }
        }, 350);
      }
      showWishlistToast('Item removed from wishlist', false);
    } else {
      if (card) {
        card.style.opacity = '1';
        card.style.transform = 'scale(1)';
      }
    }
  } catch (err) {
    console.error('Error removing from wishlist:', err);
    if (card) {
      card.style.opacity = '1';
      card.style.transform = 'scale(1)';
    }
  }
}

// Move to cart from wishlist page
function moveToCartFromWishlist(name, price, image, pid, btnEl) {
  if (typeof addToCart === 'function') {
    addToCart(name, price, image, btnEl);
    showWishlistToast(`Added "${name}" to cart!`, true);
  }
}

// Toast notification for Wishlist actions
function showWishlistToast(message, isSuccess = true) {
  let toast = document.getElementById('wishlist-toast');
  if (!toast) {
    toast = document.createElement('div');
    toast.id = 'wishlist-toast';
    toast.className = 'notification';
    document.body.appendChild(toast);
  }

  toast.style.borderColor = isSuccess ? '#f43f5e' : '#64748b';
  toast.innerHTML = `<i class="fas fa-heart" style="color: ${isSuccess ? '#f43f5e' : '#94a3b8'};"></i> <span>${message}</span>`;
  toast.classList.add('show');

  setTimeout(() => {
    toast.classList.remove('show');
  }, 2200);
}

// Auto initialize on DOM ready
document.addEventListener('DOMContentLoaded', initWishlist);
