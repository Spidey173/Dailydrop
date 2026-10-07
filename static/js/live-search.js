/**
 * Daily Drop - Instant Live Search with Autocomplete Dropdown
 */

(function () {
  let searchDebounceTimer = null;
  let activeSelectedIndex = -1;

  function initLiveSearch() {
    const searchInputs = document.querySelectorAll('#searchInput, .search-bar input[type="text"]');
    if (!searchInputs || searchInputs.length === 0) return;

    searchInputs.forEach(input => {
      const searchBar = input.closest('.search-bar');
      if (!searchBar) return;

      // Create dropdown container if not present
      let dropdown = searchBar.querySelector('.search-autocomplete-dropdown');
      if (!dropdown) {
        dropdown = document.createElement('div');
        dropdown.className = 'search-autocomplete-dropdown';
        searchBar.appendChild(dropdown);
      }

      // Input listener with debounce
      input.addEventListener('input', function () {
        const query = this.value.trim();
        clearTimeout(searchDebounceTimer);

        if (query.length === 0) {
          closeDropdown(dropdown);
          return;
        }

        searchDebounceTimer = setTimeout(() => {
          performAutocompleteSearch(query, dropdown, input);
        }, 160);
      });

      // Keyboard navigation (Arrow Up, Arrow Down, Enter, Escape)
      input.addEventListener('keydown', function (e) {
        if (!dropdown.classList.contains('show')) return;

        const items = dropdown.querySelectorAll('.search-suggestion-item');
        if (items.length === 0) return;

        if (e.key === 'ArrowDown') {
          e.preventDefault();
          activeSelectedIndex = (activeSelectedIndex + 1) % items.length;
          updateSelectedSuggestion(items, activeSelectedIndex);
        } else if (e.key === 'ArrowUp') {
          e.preventDefault();
          activeSelectedIndex = (activeSelectedIndex - 1 + items.length) % items.length;
          updateSelectedSuggestion(items, activeSelectedIndex);
        } else if (e.key === 'Enter') {
          if (activeSelectedIndex >= 0 && activeSelectedIndex < items.length) {
            e.preventDefault();
            items[activeSelectedIndex].click();
          }
        } else if (e.key === 'Escape') {
          closeDropdown(dropdown);
        }
      });

      // Focus listener
      input.addEventListener('focus', function () {
        if (this.value.trim().length > 0 && dropdown.children.length > 0) {
          dropdown.classList.add('show');
        }
      });
    });

    // Close on click outside
    document.addEventListener('click', function (e) {
      if (!e.target.closest('.search-bar')) {
        document.querySelectorAll('.search-autocomplete-dropdown.show').forEach(d => closeDropdown(d));
      }
    });
  }

  // Update visual selection with keyboard
  function updateSelectedSuggestion(items, index) {
    items.forEach((item, i) => {
      if (i === index) {
        item.classList.add('selected');
        item.scrollIntoView({ block: 'nearest' });
      } else {
        item.classList.remove('selected');
      }
    });
  }

  // Perform search query via backend API or fallback to window.productsDB
  async function performAutocompleteSearch(query, dropdown, inputEl) {
    activeSelectedIndex = -1;
    let results = [];

    try {
      const res = await fetch(`/api/v1/products/search?q=${encodeURIComponent(query)}&limit=7`);
      if (res.ok) {
        const data = await res.json();
        if (data.success && Array.isArray(data.results)) {
          results = data.results;
        }
      }
    } catch (err) {
      console.debug('API search error, falling back to local DB:', err);
    }

    // Fallback to client-side window.productsDB if backend is offline/empty
    if (results.length === 0 && Array.isArray(window.productsDB)) {
      const lowerQ = query.toLowerCase();
      results = window.productsDB
        .filter(p => (p.title || '').toLowerCase().includes(lowerQ) ||
                     (p.category || '').toLowerCase().includes(lowerQ) ||
                     (p.subcategory || '').toLowerCase().includes(lowerQ))
        .slice(0, 7)
        .map(p => ({
          product_id: p.id,
          name: p.title,
          price: p.price,
          category: p.category,
          subcategory: p.subcategory,
          image_path: p.image
        }));
    }

    renderAutocompleteDropdown(results, query, dropdown, inputEl);
  }

  // Render suggestion items inside dropdown
  function renderAutocompleteDropdown(results, query, dropdown, inputEl) {
    dropdown.innerHTML = '';

    if (results.length === 0) {
      dropdown.innerHTML = `
        <div class="search-dropdown-empty">
          <i class="fas fa-search"></i>
          <div>No matching products found for "<strong>${escapeHtml(query)}</strong>"</div>
        </div>
      `;
      dropdown.classList.add('show');
      return;
    }

    // Header
    const header = document.createElement('div');
    header.className = 'search-dropdown-header';
    header.innerHTML = `
      <span>Quick Matches (${results.length})</span>
      <span>Press &uarr;&darr; to navigate</span>
    `;
    dropdown.appendChild(header);

    // Items list
    results.forEach((item, index) => {
      const itemEl = document.createElement('div');
      itemEl.className = 'search-suggestion-item';
      itemEl.dataset.index = index;

      const highlightedName = highlightMatch(item.name || item.title || '', query);
      const categoryLabel = item.category || 'Grocery';
      const priceVal = Number(item.price || 0).toFixed(2);
      const imageSrc = item.image_path || item.image || '/static/logo.webp';
      const cleanName = (item.name || item.title || '').replace(/'/g, "\\'");

      itemEl.innerHTML = `
        <img src="${imageSrc}" alt="${escapeHtml(item.name || '')}" class="suggestion-thumb" onerror="this.src='/static/logo.webp'" />
        <div class="suggestion-info">
          <div class="suggestion-title">${highlightedName}</div>
          <div class="suggestion-meta">
            <span class="suggestion-category">${escapeHtml(categoryLabel)}</span>
            <span class="suggestion-price">Rs. ${priceVal}</span>
          </div>
        </div>
        <button type="button" class="suggestion-quick-add" title="Add to Cart" onclick="event.stopPropagation(); if (typeof addToCart === 'function') { addToCart('${cleanName}', ${priceVal}, '${imageSrc}', this); }">
          <i class="fas fa-plus"></i> Add
        </button>
      `;

      // Click to open details or perform page search
      itemEl.addEventListener('click', function () {
        if (typeof showDetails === 'function') {
          showDetails(item.name || item.title, `Rs.${priceVal}`, imageSrc);
          const modal = document.getElementById('productModal');
          if (modal && window.bootstrap) {
            new bootstrap.Modal(modal).show();
          }
        }
        closeDropdown(dropdown);
      });

      dropdown.appendChild(itemEl);
    });

    dropdown.classList.add('show');
  }

  function closeDropdown(dropdown) {
    if (dropdown) {
      dropdown.classList.remove('show');
      activeSelectedIndex = -1;
    }
  }

  function highlightMatch(text, query) {
    if (!query) return escapeHtml(text);
    const escapedQuery = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const regex = new RegExp(`(${escapedQuery})`, 'gi');
    return escapeHtml(text).replace(regex, '<mark>$1</mark>');
  }

  function escapeHtml(str) {
    if (!str) return '';
    return str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  // Initialize on DOM ready
  document.addEventListener('DOMContentLoaded', initLiveSearch);
})();
