/**
 * Daily Drop - Universal Product Modal & Graphical Explanation Engine
 */

let globalChartInstance = null;
let currentActiveProfile = null;
let isChartJSLoading = false;

// Ensure Chart.js is loaded (preloads immediately or on demand)
function ensureChartJS(callback) {
  if (typeof Chart !== 'undefined') {
    if (callback) callback();
    return;
  }
  if (isChartJSLoading) {
    const checkInterval = setInterval(() => {
      if (typeof Chart !== 'undefined') {
        clearInterval(checkInterval);
        if (callback) callback();
      }
    }, 50);
    return;
  }
  isChartJSLoading = true;
  const script = document.createElement('script');
  script.src = 'https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js';
  script.onload = () => {
    isChartJSLoading = false;
    if (callback) callback();
  };
  script.onerror = () => {
    isChartJSLoading = false;
    console.warn('Chart.js CDN unavailable; visual metric bars active as graphical explanation.');
  };
  document.head.appendChild(script);
}

// Category classification helper
function getCategoryGroup(categoryStr = '', titleStr = '') {
  const cat = (categoryStr || '').toLowerCase();
  const title = (titleStr || '').toLowerCase();

  if (cat.includes('baby') || title.includes('baby') || title.includes('diaper') || title.includes('huggies') || title.includes('pampers') || title.includes('rusk') || title.includes('cerelac')) {
    return 'baby';
  }
  if (cat.includes('personal') || title.includes('shampoo') || title.includes('soap') || title.includes('cream') || title.includes('lotion') || title.includes('toothpaste') || title.includes('whisper') || title.includes('dove') || title.includes('dettol')) {
    return 'personal';
  }
  if (cat.includes('household') || title.includes('cleaner') || title.includes('detergent') || title.includes('air') || title.includes('fresh') || title.includes('surf') || title.includes('harpic') || title.includes('lizol') || title.includes('comfort')) {
    return 'household';
  }
  if (cat.includes('home') || cat.includes('kitchen') || title.includes('apron') || title.includes('stand') || title.includes('bottle') || title.includes('pan') || title.includes('cookware') || title.includes('container') || title.includes('foil')) {
    return 'kitchen';
  }
  if (cat.includes('beverage') || title.includes('juice') || title.includes('drink') || title.includes('coke') || title.includes('pepsi') || title.includes('lassi') || title.includes('water') || title.includes('tea') || title.includes('coffee') || title.includes('frooti')) {
    return 'beverage';
  }
  if (cat.includes('snack') || title.includes('chip') || title.includes('biscuit') || title.includes('chocolate') || title.includes('kurkure') || title.includes('lays') || title.includes('oreo') || title.includes('kitkat') || title.includes('maggie')) {
    return 'snack';
  }
  return 'food';
}

// Deterministic integer hash for consistent metrics
function hashString(str) {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    hash = (hash << 5) - hash + str.charCodeAt(i);
    hash |= 0;
  }
  return Math.abs(hash);
}

// Generate metric profiles dynamically
function getProductMetricsProfile(title, category, price) {
  const group = getCategoryGroup(category, title);
  const hash = hashString(title);
  const val = (index, min = 60, max = 98) => min + ((hash + index * 17) % (max - min + 1));

  if (group === 'baby') {
    return {
      type: 'baby',
      chartTitle: 'Baby Safety & Care Index',
      labels: ['Hypoallergenic', 'Gentle Skin', 'Pediatrician', 'Eco Material', 'Safety Cert.'],
      data: [val(1, 85, 99), val(2, 90, 99), val(3, 88, 98), val(4, 75, 95), val(5, 92, 100)],
      accentColor: '#38BDF8',
      gradientColor: 'rgba(56, 189, 248, 0.35)',
      borderColor: '#38BDF8',
      badges: [
        { icon: 'fas fa-baby', text: 'Pediatrician Approved', color: '#38BDF8' },
        { icon: 'fas fa-shield-alt', text: '100% Paraben-Free', color: '#34D399' },
        { icon: 'fas fa-feather', text: 'Ultra Soft Touch', color: '#F472B6' }
      ],
      highlights: [
        { label: 'Age Group', value: '0 - 36 Months' },
        { label: 'Dermatology', value: 'Clinically Tested' },
        { label: 'Skin Type', value: 'Sensitive Skin' }
      ]
    };
  }

  if (group === 'personal') {
    return {
      type: 'personal',
      chartTitle: 'Skin & Wellness Profile',
      labels: ['Moisture Lock', 'Botanical Extracts', 'pH Balance', 'Gentle Cleanse', 'Fresh Fragrance'],
      data: [val(1, 75, 96), val(2, 70, 98), val(3, 85, 99), val(4, 80, 95), val(5, 65, 92)],
      accentColor: '#EC4899',
      gradientColor: 'rgba(236, 72, 153, 0.35)',
      borderColor: '#EC4899',
      badges: [
        { icon: 'fas fa-sparkles', text: 'Dermatologist Tested', color: '#EC4899' },
        { icon: 'fas fa-leaf', text: 'Cruelty Free', color: '#34D399' },
        { icon: 'fas fa-tint', text: 'pH 5.5 Balanced', color: '#60A5FA' }
      ],
      highlights: [
        { label: 'Formula', value: 'Toxin Free' },
        { label: 'Suitability', value: 'All Skin Types' },
        { label: 'Origin', value: '100% Pure Botanical' }
      ]
    };
  }

  if (group === 'household') {
    return {
      type: 'household',
      chartTitle: 'Performance & Safety Profile',
      labels: ['Cleaning Power', 'Eco-Debris Score', 'Non-Toxic Index', 'Odor Defense', 'Long Lasting'],
      data: [val(1, 82, 98), val(2, 70, 92), val(3, 78, 96), val(4, 85, 99), val(5, 80, 95)],
      accentColor: '#F59E0B',
      gradientColor: 'rgba(245, 158, 11, 0.35)',
      borderColor: '#F59E0B',
      badges: [
        { icon: 'fas fa-shield-virus', text: '99.9% Germ Shield', color: '#F59E0B' },
        { icon: 'fas fa-seedling', text: 'Eco Biodegradable', color: '#34D399' },
        { icon: 'fas fa-home', text: 'Safe around Pets', color: '#A78BFA' }
      ],
      highlights: [
        { label: 'Child Lock', value: 'Safety Cap Fitted' },
        { label: 'Action Time', value: 'Instant 30 Sec' },
        { label: 'Fragrance', value: 'Fresh Citrus Breeze' }
      ]
    };
  }

  if (group === 'kitchen') {
    return {
      type: 'kitchen',
      chartTitle: 'Durability & Quality Index',
      labels: ['Material Build', 'Heat Resistance', 'Ergonomics', 'Food-Grade Cert', 'Easy Cleaning'],
      data: [val(1, 88, 99), val(2, 80, 98), val(3, 85, 95), val(4, 92, 100), val(5, 82, 96)],
      accentColor: '#8B5CF6',
      gradientColor: 'rgba(139, 92, 246, 0.35)',
      borderColor: '#8B5CF6',
      badges: [
        { icon: 'fas fa-check-circle', text: 'Food-Grade Certified', color: '#8B5CF6' },
        { icon: 'fas fa-fire-alt', text: 'Heat Resistant', color: '#EF4444' },
        { icon: 'fas fa-award', text: '2-Year Warranty', color: '#F59E0B' }
      ],
      highlights: [
        { label: 'Material', value: 'BPA-Free / Stainless' },
        { label: 'Dishwasher', value: '100% Safe' },
        { label: 'Durability', value: 'Heavy Duty Grade' }
      ]
    };
  }

  if (group === 'beverage') {
    return {
      type: 'beverage',
      chartTitle: 'Hydration & Nutrient Matrix',
      labels: ['Hydration Index', 'Vitamins/Minerals', 'Low-Sugar Score', 'Energy Boost', 'Natural Purity'],
      data: [val(1, 85, 99), val(2, 65, 95), val(3, 60, 90), val(4, 70, 98), val(5, 80, 98)],
      accentColor: '#06B6D4',
      gradientColor: 'rgba(6, 182, 212, 0.35)',
      borderColor: '#06B6D4',
      badges: [
        { icon: 'fas fa-glass-cheers', text: '100% Refreshing', color: '#06B6D4' },
        { icon: 'fas fa-bolt', text: 'Instant Energy', color: '#F59E0B' },
        { icon: 'fas fa-snowflake', text: 'Best Served Chilled', color: '#60A5FA' }
      ],
      highlights: [
        { label: 'Calories', value: `${val(1, 40, 180)} kcal` },
        { label: 'Serving Size', value: 'Standard Pack' },
        { label: 'Storage', value: 'Keep Cold (2-5°C)' }
      ]
    };
  }

  if (group === 'snack') {
    return {
      type: 'snack',
      chartTitle: 'Snack Taste & Energy Matrix',
      labels: ['Crunchy Index', 'Flavor Intensity', 'Protein Score', 'Fiber Boost', 'Energy Value'],
      data: [val(1, 80, 99), val(2, 85, 98), val(3, 40, 75), val(4, 30, 70), val(5, 75, 95)],
      accentColor: '#F97316',
      gradientColor: 'rgba(249, 115, 22, 0.35)',
      borderColor: '#F97316',
      badges: [
        { icon: 'fas fa-utensils', text: 'Crispy & Crunchy', color: '#F97316' },
        { icon: 'fas fa-ban', text: 'Zero Trans Fat', color: '#34D399' },
        { icon: 'fas fa-fire', text: 'High Energy', color: '#EF4444' }
      ],
      highlights: [
        { label: 'Calories', value: `${val(1, 150, 450)} kcal` },
        { label: 'Pack Size', value: 'Standard Pouch' },
        { label: 'Shelf Life', value: '6 Months' }
      ]
    };
  }

  // Standard Food / Grocery / Vegetables / Dairy
  return {
    type: 'food',
    chartTitle: 'Nutritional Macro Matrix (per 100g)',
    labels: ['Protein', 'Carbs', 'Dietary Fiber', 'Vitamins & Min.', 'Healthy Fats'],
    data: [val(1, 50, 92), val(2, 60, 95), val(3, 45, 90), val(4, 70, 98), val(5, 30, 85)],
    accentColor: '#10B981',
    gradientColor: 'rgba(16, 185, 129, 0.35)',
    borderColor: '#10B981',
    badges: [
      { icon: 'fas fa-seedling', text: '100% Fresh', color: '#10B981' },
      { icon: 'fas fa-check-double', text: 'Quality Tested', color: '#34D399' },
      { icon: 'fas fa-heartbeat', text: 'Daily Essential', color: '#EF4444' }
    ],
    highlights: [
      { label: 'Energy', value: `${val(1, 60, 320)} kcal / 100g` },
      { label: 'Freshness', value: 'Farm Sourced Today' },
      { label: 'Storage', value: 'Cool Dry Pantry' }
    ]
  };
}

// Inject fallback modal HTML if template include was not rendered
function injectProductModalHTML() {
  if (document.getElementById('productMetricsChart')) {
    return; // Modal structure with chart already present
  }

  const existing = document.getElementById('productModal');
  if (existing) {
    existing.remove();
  }

  const modalHTML = `
  <div class="modal fade" id="productModal" tabindex="-1" aria-labelledby="productModalLabel" aria-hidden="true">
    <div class="modal-dialog modal-dialog-centered modal-xl">
      <div class="modal-content glass-modal-content">
        <div class="modal-header border-0 pb-1">
          <div class="d-flex align-items-center gap-2">
            <span class="badge bg-emerald-glow" id="modalCategoryBadge"><i class="fas fa-tag me-1"></i> Category</span>
            <span class="badge bg-express-delivery"><i class="fas fa-bolt me-1"></i> 10-Min Delivery</span>
          </div>
          <button type="button" class="btn-close btn-close-white ms-auto" data-bs-dismiss="modal" aria-label="Close"></button>
        </div>
        <div class="modal-body p-4 pt-2">
          <div class="row g-4 align-items-start">
            <div class="col-lg-4 col-md-5 text-center">
              <div class="product-modal-img-wrap mb-3">
                <img id="modalImage" src="/static/product-placeholder.svg" alt="Product Image" class="img-fluid rounded-4 shadow-lg product-modal-img" onerror="this.onerror=null; this.src='/static/product-placeholder.svg';" />
              </div>
              <div class="badge-list d-flex flex-wrap justify-content-center gap-2 mb-2" id="modalBadgesContainer"></div>
            </div>
            <div class="col-lg-4 col-md-7 border-lg-end border-glass-divider">
              <h3 id="modalTitle" class="modal-product-title mb-2">Product Title</h3>
              <div class="modal-pricing-row d-flex align-items-baseline gap-2 mb-3">
                <span id="modalPrice" class="modal-price-val">Rs. 0</span>
                <span class="modal-strike-val" id="modalStrikePrice">Rs. 0</span>
                <span class="badge modal-stock-badge"><i class="fas fa-check-circle me-1"></i> In Stock</span>
              </div>
              <p id="modalDescription" class="modal-desc text-secondary mb-3">Premium quality product carefully sourced, inspected, and delivered fresh to your doorstep.</p>
              <div class="specs-box p-3 rounded-3 mb-3" id="modalHighlightsContainer"></div>
              <div class="modal-cart-actions d-flex align-items-center gap-3">
                <div class="quantity-picker d-flex align-items-center rounded-3 bg-dark-input">
                  <button type="button" class="btn btn-sm text-white px-3" onclick="updateModalQuantity(-1)"><i class="fas fa-minus"></i></button>
                  <span id="modalQuantity" class="fw-bold px-2 text-white">1</span>
                  <button type="button" class="btn btn-sm text-white px-3" onclick="updateModalQuantity(1)"><i class="fas fa-plus"></i></button>
                </div>
                <button type="button" class="btn btn-emerald-action flex-grow-1 py-2 fw-bold" onclick="addModalItemToCart()">
                  <i class="fas fa-shopping-basket me-2"></i> Add to Cart
                </button>
              </div>
            </div>
            <div class="col-lg-4 col-md-12">
              <div class="chart-card-box rounded-4 text-center h-100 d-flex flex-column justify-content-between p-3" style="background: rgba(255, 255, 255, 0.02); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 16px;">
                <div>
                  <div class="d-flex align-items-center justify-content-between mb-2 pb-2" style="border-bottom: 1px solid rgba(255, 255, 255, 0.08);">
                    <div class="text-start">
                      <span class="matrix-subtitle" style="font-size: 0.72rem; text-transform: uppercase; letter-spacing: 1px; color: #38BDF8;"><i class="fas fa-chart-pie me-1"></i> Graphical Analysis</span>
                      <h6 id="chartBoxTitle" class="matrix-main-title mb-0" style="font-weight: 700; color: #FFFFFF;">Quality & Nutritional Index</h6>
                    </div>
                    <span class="live-matrix-badge"><span class="live-pulse-dot"></span> LIVE</span>
                  </div>
                </div>
                <div class="chart-container-wrapper position-relative my-2" style="height: 200px; min-height: 200px; width: 100%; display: flex; align-items: center; justify-content: center;" id="chartContainerWrap">
                  <canvas id="productMetricsChart" style="max-height: 200px; width: 100% !important;"></canvas>
                </div>
                <div id="modalMetricBars" class="w-100 text-start px-1 my-1"></div>
                <div class="matrix-footer-tag text-center pt-2 mt-1" style="border-top: 1px solid rgba(255, 255, 255, 0.06);">
                  <span class="matrix-footnote" style="font-size: 0.75rem; color: #94A3B8;">
                    <i class="fas fa-shield-alt text-success me-1"></i> Interactive score based on lab testing & specs.
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>`;

  document.body.insertAdjacentHTML('beforeend', modalHTML);
}

// Modal Quantity Handler
let modalItemQty = 1;
function updateModalQuantity(delta) {
  modalItemQty = Math.max(1, modalItemQty + delta);
  const qtyEl = document.getElementById('modalQuantity');
  if (qtyEl) qtyEl.innerText = modalItemQty;
}

// Render instant visual metric progress bars
function renderMetricBars(profile) {
  const container = document.getElementById('modalMetricBars');
  if (!container) return;

  container.innerHTML = profile.labels.map((lbl, idx) => {
    const score = profile.data[idx] || 80;
    return `
      <div class="mb-1">
        <div class="d-flex justify-content-between text-xs mb-0" style="font-size: 0.73rem;">
          <span class="text-white-50">${lbl}</span>
          <span style="color: ${profile.accentColor}; font-weight: 700;">${score}/100</span>
        </div>
        <div class="progress" style="height: 4px; background: rgba(255, 255, 255, 0.08); border-radius: 4px;">
          <div class="progress-bar" role="progressbar" style="width: ${score}%; background: ${profile.accentColor}; border-radius: 4px; transition: width 0.6s ease;" aria-valuenow="${score}" aria-valuemin="0" aria-valuemax="100"></div>
        </div>
      </div>
    `;
  }).join('');
}

// Render or Update Chart.js Radar Instance
function renderChartJSRadar(profile) {
  const canvas = document.getElementById('productMetricsChart');
  if (!canvas) return;

  if (typeof Chart === 'undefined') {
    ensureChartJS(() => renderChartJSRadar(profile));
    return;
  }

  // Destroy previous chart instance cleanly
  if (globalChartInstance) {
    try {
      globalChartInstance.destroy();
    } catch (e) {
      console.debug('Chart cleanup:', e);
    }
    globalChartInstance = null;
  }

  try {
    const ctx = canvas.getContext('2d');
    globalChartInstance = new Chart(ctx, {
      type: 'radar',
      data: {
        labels: profile.labels,
        datasets: [{
          label: 'Score / 100',
          data: profile.data,
          backgroundColor: profile.gradientColor,
          borderColor: profile.borderColor,
          borderWidth: 2,
          pointBackgroundColor: profile.accentColor,
          pointBorderColor: '#FFFFFF',
          pointHoverBackgroundColor: '#FFFFFF',
          pointHoverBorderColor: profile.accentColor,
          pointRadius: 4,
          pointHoverRadius: 6
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: {
          duration: 600,
          easing: 'easeOutQuart'
        },
        scales: {
          r: {
            angleLines: { color: 'rgba(255, 255, 255, 0.12)' },
            grid: { color: 'rgba(255, 255, 255, 0.08)' },
            pointLabels: {
              color: '#CBD5E1',
              font: { size: 9, family: "'Plus Jakarta Sans', sans-serif", weight: '600' }
            },
            ticks: { display: false, stepSize: 25, beginAtZero: true },
            suggestedMin: 0,
            suggestedMax: 100
          }
        },
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: 'rgba(5, 20, 13, 0.95)',
            titleColor: '#F8FAFC',
            bodyColor: profile.accentColor,
            borderColor: profile.borderColor,
            borderWidth: 1,
            padding: 8,
            displayColors: false,
            callbacks: {
              label: function(context) {
                return `${context.label}: ${context.raw} / 100`;
              }
            }
          }
        }
      }
    });
  } catch (err) {
    console.warn('Radar canvas render skipped; visual metric bars active:', err);
  }
}

// Universal showDetails function called by product cards across entire site
window.showDetails = function(name, priceStr, image, categoryHint = '') {
  modalItemQty = 1;
  const qtyEl = document.getElementById('modalQuantity');
  if (qtyEl) qtyEl.innerText = 1;

  // Ensure modal HTML exists
  injectProductModalHTML();

  // Find product details from productsDB or fallback
  const catalog = window.productsDB || window.serverInitialProducts || [];
  const productMatch = catalog.find(p => (p.title === name || p.name === name)) || {};
  const category = productMatch.category || categoryHint || window.categoryName || 'Daily Essential';
  const description = productMatch.description || 'Premium quality product carefully sourced, inspected, and delivered fresh to your doorstep.';

  // Format Price
  let rawPrice = 0;
  if (typeof priceStr === 'number') {
    rawPrice = priceStr;
  } else if (typeof priceStr === 'string') {
    rawPrice = parseFloat(priceStr.replace(/[^0-9.]/g, '')) || 0;
  }
  const formattedPrice = `Rs. ${rawPrice.toFixed(2)}`;
  const strikePrice = `Rs. ${(rawPrice * 1.15).toFixed(2)}`;

  // Populate basic text fields
  const titleEl = document.getElementById('modalTitle');
  if (titleEl) titleEl.innerText = name;

  const priceEl = document.getElementById('modalPrice');
  if (priceEl) priceEl.innerText = formattedPrice;

  const strikeEl = document.getElementById('modalStrikePrice');
  if (strikeEl) strikeEl.innerText = strikePrice;

  const imgEl = document.getElementById('modalImage');
  if (imgEl) {
    imgEl.src = image || '/static/product-placeholder.svg';
    imgEl.onerror = function() { this.onerror = null; this.src = '/static/product-placeholder.svg'; };
  }

  const descEl = document.getElementById('modalDescription');
  if (descEl) descEl.innerText = description;

  const catBadge = document.getElementById('modalCategoryBadge');
  if (catBadge) catBadge.innerHTML = `<i class="fas fa-tag me-1"></i> ${category}`;

  // Get dynamic metric profile for graphical explanation
  const profile = getProductMetricsProfile(name, category, rawPrice);
  currentActiveProfile = profile;

  // Render Badges
  const badgesContainer = document.getElementById('modalBadgesContainer');
  if (badgesContainer) {
    badgesContainer.innerHTML = profile.badges.map(b => `
      <span class="badge glass-badge" style="border-color: ${b.color}; color: ${b.color}; background: rgba(255, 255, 255, 0.04);">
        <i class="${b.icon} me-1"></i> ${b.text}
      </span>
    `).join('');
  }

  // Render Spec Highlights Table
  const highlightsContainer = document.getElementById('modalHighlightsContainer');
  if (highlightsContainer) {
    highlightsContainer.innerHTML = profile.highlights.map(h => `
      <div class="d-flex justify-content-between align-items-center py-1 border-bottom border-glass-subtle text-xs" style="font-size: 0.8rem;">
        <span class="text-secondary"><i class="fas fa-angle-right me-1 text-primary"></i> ${h.label}</span>
        <span class="fw-semibold text-white">${h.value}</span>
      </div>
    `).join('');
  }

  // Set Chart Title
  const chartTitleEl = document.getElementById('chartBoxTitle');
  if (chartTitleEl) {
    chartTitleEl.innerHTML = profile.chartTitle;
  }

  // Render Instant Visual Metric Progress Bars
  renderMetricBars(profile);

  // Show Bootstrap Modal
  const modalEl = document.getElementById('productModal');
  if (modalEl && typeof bootstrap !== 'undefined' && bootstrap.Modal) {
    const bsModal = bootstrap.Modal.getOrCreateInstance(modalEl);
    
    // Bind shown event once to render Chart.js radar cleanly after layout transition
    const onShown = function() {
      modalEl.removeEventListener('shown.bs.modal', onShown);
      renderChartJSRadar(profile);
    };
    modalEl.addEventListener('shown.bs.modal', onShown);
    
    bsModal.show();
    
    // Also trigger rendering after 150ms timeout as fallback for fast opens
    setTimeout(() => {
      renderChartJSRadar(profile);
    }, 150);
  } else if (modalEl) {
    modalEl.classList.add('show');
    modalEl.style.display = 'block';
    renderChartJSRadar(profile);
  }
};

// Also expose legacy function name for backwards compatibility
window.addToCartFromModal = function() {
  window.addModalItemToCart();
};

// Add item to cart from modal
window.addModalItemToCart = function() {
  const titleEl = document.getElementById('modalTitle');
  const name = titleEl ? titleEl.innerText.trim() : 'Product';
  const priceEl = document.getElementById('modalPrice');
  const priceText = priceEl ? priceEl.innerText : '0';
  const imgEl = document.getElementById('modalImage');
  const image = imgEl ? imgEl.src : '/static/product-placeholder.svg';
  const price = parseFloat(priceText.replace(/[^0-9.]/g, '')) || 0;
  const qtyToAdd = Math.max(1, parseInt(modalItemQty) || 1);

  // 1. Hide modal cleanly using Bootstrap instance
  const modalEl = document.getElementById('productModal');
  if (modalEl && typeof bootstrap !== 'undefined' && bootstrap.Modal) {
    const bsModal = bootstrap.Modal.getInstance(modalEl) || bootstrap.Modal.getOrCreateInstance(modalEl);
    if (bsModal) {
      bsModal.hide();
    }
  } else if (modalEl) {
    modalEl.classList.remove('show');
    modalEl.style.display = 'none';
  }

  // 2. Cleanup backdrop and restore body scroll immediately
  setTimeout(() => {
    document.querySelectorAll('.modal-backdrop').forEach(el => el.remove());
    document.body.classList.remove('modal-open');
    document.body.style.removeProperty('overflow');
    document.body.style.removeProperty('padding-right');
  }, 150);

  // 3. User login validation
  if (typeof isUserLoggedIn === 'function' && !isUserLoggedIn()) {
    if (typeof showGuestLoginAlert === 'function') {
      showGuestLoginAlert();
    }
    return;
  }

  // 4. Update cart in localStorage
  let cart = JSON.parse(localStorage.getItem('cart')) || [];
  const existingItem = cart.find(item => item.name === name);
  if (existingItem) {
    existingItem.quantity += qtyToAdd;
  } else {
    cart.push({
      name: name,
      price: price,
      image: image,
      quantity: qtyToAdd
    });
  }
  localStorage.setItem('cart', JSON.stringify(cart));

  // 5. Visual feedback and updates
  if (typeof animateFlyToCart === 'function') {
    animateFlyToCart(image, imgEl || window.event);
  }
  if (typeof updateCartCount === 'function') {
    updateCartCount();
  }
  if (typeof updateProductButtons === 'function') {
    updateProductButtons();
  }
  if (typeof showAddedToCartAlert === 'function') {
    showAddedToCartAlert(name);
  }

  window.dispatchEvent(new Event('storage'));
};

// Initialize modal on DOM load and preload Chart.js
document.addEventListener('DOMContentLoaded', () => {
  injectProductModalHTML();
  ensureChartJS();
});
