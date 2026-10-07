/**
 * Daily Drop - Interactive Product Modal & Chart.js Metrics Engine
 */

let globalChartInstance = null;
let currentActiveProfile = null;
let isChartJSLoading = false;

// Ensure Chart.js is loaded dynamically if not already in document
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
  script.src = 'https://cdn.jsdelivr.net/npm/chart.js';
  script.onload = () => {
    isChartJSLoading = false;
    if (callback) callback();
  };
  script.onerror = () => {
    isChartJSLoading = false;
    console.warn('Could not load Chart.js CDN, rendering visual metric bars fallback.');
    if (currentActiveProfile) renderFallbackMatrix(currentActiveProfile);
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

// Generate deterministic integer hash from string
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

// Global modal builder
function injectProductModalHTML() {
  if (document.getElementById('productModal')) {
    const existing = document.getElementById('productModal');
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
            
            <!-- Left Column: Product Image & Badges -->
            <div class="col-lg-4 col-md-5 text-center">
              <div class="product-modal-img-wrap mb-3">
                <img id="modalImage" src="" alt="Product Image" class="img-fluid rounded-4 shadow-lg product-modal-img" onerror="this.src='/static/logo.webp'" />
              </div>
              <div class="badge-list d-flex flex-wrap justify-content-center gap-2 mb-2" id="modalBadgesContainer">
                <!-- Badges injected dynamically -->
              </div>
            </div>

            <!-- Middle Column: Product Details & Cart Actions -->
            <div class="col-lg-4 col-md-7 border-lg-end border-glass-divider">
              <h3 id="modalTitle" class="modal-product-title mb-2">Product Title</h3>
              
              <div class="modal-pricing-row d-flex align-items-baseline gap-2 mb-3">
                <span id="modalPrice" class="modal-price-val">Rs. 0</span>
                <span class="modal-strike-val" id="modalStrikePrice">Rs. 0</span>
                <span class="badge modal-stock-badge"><i class="fas fa-check-circle me-1"></i> In Stock</span>
              </div>
              
              <p id="modalDescription" class="modal-desc text-secondary mb-3">
                Detailed description goes here...
              </p>

              <!-- Quick Highlights Spec Table -->
              <div class="specs-box p-3 rounded-3 mb-3" id="modalHighlightsContainer">
                <!-- Injected highlights -->
              </div>

              <!-- Quantity Selector & Add to Cart -->
              <div class="modal-cart-actions d-flex align-items-center gap-3">
                <div class="quantity-picker d-flex align-items-center rounded-3 bg-dark-input">
                  <button class="btn btn-sm text-white px-3" onclick="updateModalQuantity(-1)"><i class="fas fa-minus"></i></button>
                  <span id="modalQuantity" class="fw-bold px-2 text-white">1</span>
                  <button class="btn btn-sm text-white px-3" onclick="updateModalQuantity(1)"><i class="fas fa-plus"></i></button>
                </div>
                <button class="btn btn-emerald-action flex-grow-1 py-2 fw-bold" onclick="addModalItemToCart()">
                  <i class="fas fa-shopping-basket me-2"></i> Add to Cart
                </button>
              </div>
            </div>

            <!-- Right Column: Interactive Chart.js Canvas -->
            <div class="col-lg-4 col-md-12">
              <div class="chart-card-box rounded-4 text-center h-100 d-flex flex-column justify-content-between">
                <div>
                  <div class="d-flex align-items-center justify-content-between mb-2 pb-2" style="border-bottom: 1px solid rgba(255, 255, 255, 0.08);">
                    <div class="text-start">
                      <span class="matrix-subtitle"><i class="fas fa-microscope text-primary me-1"></i> AI Radar Matrix</span>
                      <h6 id="chartBoxTitle" class="matrix-main-title mb-0">Quality Index</h6>
                    </div>
                    <span class="live-matrix-badge">
                      <span class="live-pulse-dot"></span> LIVE
                    </span>
                  </div>
                </div>
                
                <div class="chart-container-wrapper flex-grow-1 position-relative d-flex align-items-center justify-content-center my-1" style="min-height: 250px; max-height: 280px; height: 260px;" id="chartContainerWrap">
                  <canvas id="productMetricsChart"></canvas>
                </div>
                
                <div class="matrix-footer-tag text-center pt-2 mt-1">
                  <span class="matrix-footnote">
                    <i class="fas fa-shield-alt text-success me-1"></i> Interactive score based on lab testing & specs.
                  </span>
                </div>
              </div>
            </div>

          </div>
        </div>
      </div>
    </div>
  </div>
  `;

  document.body.insertAdjacentHTML('beforeend', modalHTML);

  // Bind shown.bs.modal to ensure Chart.js canvas renders cleanly after layout transition
  const modalEl = document.getElementById('productModal');
  modalEl.addEventListener('shown.bs.modal', function () {
    if (currentActiveProfile) {
      renderChartJSRadar(currentActiveProfile);
    }
  });
}

// Modal Quantity Handler
let modalItemQty = 1;
function updateModalQuantity(delta) {
  modalItemQty = Math.max(1, modalItemQty + delta);
  const qtyEl = document.getElementById('modalQuantity');
  if (qtyEl) qtyEl.innerText = modalItemQty;
}

// Universal showDetails Override
window.showDetails = function(name, priceStr, image, categoryHint = '') {
  modalItemQty = 1;
  const qtyEl = document.getElementById('modalQuantity');
  if (qtyEl) qtyEl.innerText = 1;

  // Make sure modal HTML exists
  if (!document.getElementById('productModal') || !document.getElementById('productMetricsChart')) {
    injectProductModalHTML();
  }

  // Parse product details from global DB if available
  const productMatch = (window.productsDB || []).find(p => p.title === name || p.name === name) || {};
  const category = productMatch.category || categoryHint || window.categoryName || 'General';
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
  if (imgEl) imgEl.src = image || '/static/logo.webp';

  const descEl = document.getElementById('modalDescription');
  if (descEl) descEl.innerText = description;

  const catBadge = document.getElementById('modalCategoryBadge');
  if (catBadge) catBadge.innerHTML = `<i class="fas fa-tag me-1"></i> ${category}`;

  // Get dynamic metric profile
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
      <div class="d-flex justify-content-between align-items-center py-1 border-bottom border-glass-subtle text-xs">
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

  // Trigger Bootstrap Modal
  const modalEl = document.getElementById('productModal');
  const bsModal = bootstrap.Modal.getOrCreateInstance(modalEl);
  bsModal.show();

  // Render Chart immediately / ensure Chart.js is ready
  ensureChartJS(() => {
    renderChartJSRadar(profile);
  });
};

// Also expose legacy function name for safety
window.addToCartFromModal = function() {
  window.addModalItemToCart();
};

// Render or Update Chart.js Instance
function renderChartJSRadar(profile) {
  const canvas = document.getElementById('productMetricsChart');
  if (!canvas) return;

  if (typeof Chart === 'undefined') {
    ensureChartJS(() => renderChartJSRadar(profile));
    return;
  }

  const ctx = canvas.getContext('2d');

  // Destroy previous chart instance to avoid overlapping/ghosting
  if (globalChartInstance) {
    globalChartInstance.destroy();
    globalChartInstance = null;
  }

  try {
    globalChartInstance = new Chart(ctx, {
      type: 'radar',
      data: {
        labels: profile.labels,
        datasets: [{
          label: 'Score / 100',
          data: profile.data,
          backgroundColor: profile.gradientColor,
          borderColor: profile.borderColor,
          borderWidth: 2.5,
          pointBackgroundColor: profile.accentColor,
          pointBorderColor: '#FFFFFF',
          pointHoverBackgroundColor: '#FFFFFF',
          pointHoverBorderColor: profile.accentColor,
          pointRadius: 4.5,
          pointHoverRadius: 7
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        layout: {
          padding: {
            top: 6,
            bottom: 6,
            left: 10,
            right: 10
          }
        },
        animation: {
          duration: 750,
          easing: 'easeOutQuart'
        },
        scales: {
          r: {
            angleLines: {
              color: 'rgba(255, 255, 255, 0.12)'
            },
            grid: {
              color: 'rgba(255, 255, 255, 0.08)'
            },
            pointLabels: {
              color: '#E2E8F0',
              padding: 6,
              font: {
                size: 10,
                family: "'Plus Jakarta Sans', sans-serif",
                weight: '600'
              }
            },
            ticks: {
              display: false,
              stepSize: 20,
              beginAtZero: true
            },
            suggestedMin: 0,
            suggestedMax: 100
          }
        },
        plugins: {
          legend: {
            display: false
          },
          tooltip: {
            backgroundColor: 'rgba(5, 20, 13, 0.95)',
            titleColor: '#F8FAFC',
            bodyColor: profile.accentColor,
            borderColor: profile.borderColor,
            borderWidth: 1,
            padding: 10,
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
    console.error('Error rendering Radar chart:', err);
    renderFallbackMatrix(profile);
  }
}

// Fallback HTML Progress Bars if Chart.js encounters an error
function renderFallbackMatrix(profile) {
  const wrap = document.getElementById('chartContainerWrap');
  if (!wrap) return;

  wrap.innerHTML = `
    <div class="w-100 p-2 text-start">
      ${profile.labels.map((lbl, idx) => `
        <div class="mb-2">
          <div class="d-flex justify-content-between text-xs mb-1">
            <span class="text-white fw-semibold" style="font-size: 0.8rem;">${lbl}</span>
            <span class="text-accent fw-bold" style="font-size: 0.8rem;">${profile.data[idx]}/100</span>
          </div>
          <div class="progress" style="height: 6px; background: rgba(255,255,255,0.1); border-radius: 4px;">
            <div class="progress-bar" role="progressbar" style="width: ${profile.data[idx]}%; background: ${profile.accentColor}; border-radius: 4px;" aria-valuenow="${profile.data[idx]}" aria-valuemin="0" aria-valuemax="100"></div>
          </div>
        </div>
      `).join('')}
    </div>
  `;
}

// Add item to cart from modal
window.addModalItemToCart = function() {
  const titleEl = document.getElementById('modalTitle');
  const name = titleEl ? titleEl.innerText : 'Product';
  const priceText = document.getElementById('modalPrice').innerText;
  const image = document.getElementById('modalImage').src;
  const price = parseFloat(priceText.replace(/[^0-9.]/g, '')) || 0;
  const modalImgEl = document.getElementById('modalImage');

  for (let i = 0; i < modalItemQty; i++) {
    if (typeof addToCart === 'function') {
      addToCart(name, price, image, modalImgEl);
    }
  }

  // Hide modal
  const modalEl = document.getElementById('productModal');
  const bsModal = bootstrap.Modal.getInstance(modalEl);
  if (bsModal) bsModal.hide();
};

// Initialize modal on DOM load and preload Chart.js
document.addEventListener('DOMContentLoaded', () => {
  injectProductModalHTML();
  ensureChartJS();
});
