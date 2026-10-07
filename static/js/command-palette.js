/**
 * Daily Drop - Cmd + K Command Palette & Web Voice Search System
 */

(function () {
  let isPaletteOpen = false;
  let selectedIndex = 0;
  let currentFilteredItems = [];
  let recognitionInstance = null;
  let isListening = false;

  // Primary Navigation Shortcuts (Cleaned: Theme shortcut removed)
  const defaultShortcuts = [
    { type: 'nav', title: 'Go to Shopping Cart', icon: 'fas fa-shopping-cart', badge: 'Cart', url: '/cart' },
    { type: 'nav', title: 'View My Orders & Receipts', icon: 'fas fa-box-open', badge: 'Orders', url: '/orders' },
    { type: 'nav', title: 'Browse Fresh Fruits & Vegetables', icon: 'fas fa-apple-alt', badge: 'Category', url: '/vegetables' },
    { type: 'nav', title: 'Browse Dairy & Breakfast', icon: 'fas fa-cheese', badge: 'Category', url: '/dairy_breakfast' },
    { type: 'nav', title: 'Browse Refreshing Beverages', icon: 'fas fa-glass-whiskey', badge: 'Category', url: '/beverages' },
    { type: 'nav', title: 'Browse Snacks & Munchies', icon: 'fas fa-cookie-bite', badge: 'Category', url: '/snacks' },
    { type: 'nav', title: 'Browse Baby Care Essentials', icon: 'fas fa-baby', badge: 'Category', url: '/baby_care' },
    { type: 'nav', title: 'Browse Household Cleaning', icon: 'fas fa-broom', badge: 'Category', url: '/household_items' },
    { type: 'nav', title: 'Browse Home & Kitchen Utensils', icon: 'fas fa-utensils', badge: 'Category', url: '/home_kitchen' },
    { type: 'nav', title: 'Browse Personal Care & Wellness', icon: 'fas fa-pump-soap', badge: 'Category', url: '/personal_care' }
  ];

  // Inject Command Palette DOM into body
  function injectPaletteDOM() {
    if (document.getElementById('cmdPaletteBackdrop')) return;

    const html = `
      <div id="cmdPaletteBackdrop" class="cmd-backdrop">
        <div class="cmd-modal-card">
          
          <!-- Search Header -->
          <div class="cmd-header">
            <i class="fas fa-search cmd-search-icon"></i>
            <input type="text" id="cmdSearchInput" placeholder="Type a product or command... (e.g. 'Milk', 'Cart')" autocomplete="off" />
            <div class="cmd-header-actions">
              <button type="button" id="cmdVoiceBtn" class="cmd-voice-btn" title="Voice Search (Click & Speak)">
                <i class="fas fa-microphone"></i>
              </button>
              <span class="cmd-key-hint"><kbd>ESC</kbd> to close</span>
            </div>
          </div>

          <!-- Listening Bar Alert -->
          <div id="cmdVoiceStatus" class="cmd-voice-status" style="display: none;">
            <div class="cmd-voice-wave">
              <span></span><span></span><span></span><span></span>
            </div>
            <span id="cmdVoiceMsg">Listening... Speak now!</span>
          </div>

          <!-- Results List Container -->
          <div class="cmd-body" id="cmdResultsList">
            <!-- Dynamic items loaded here -->
          </div>

          <!-- Footer Tips -->
          <div class="cmd-footer">
            <span><kbd>↑</kbd> <kbd>↓</kbd> Navigate</span>
            <span><kbd>↵</kbd> Select</span>
            <span><kbd>⌘K</kbd> Toggle Palette</span>
          </div>

        </div>
      </div>
    `;

    document.body.insertAdjacentHTML('beforeend', html);

    // Bind Event Listeners
    const backdrop = document.getElementById('cmdPaletteBackdrop');
    const input = document.getElementById('cmdSearchInput');
    const voiceBtn = document.getElementById('cmdVoiceBtn');

    backdrop.addEventListener('click', (e) => {
      if (e.target === backdrop) closeCommandPalette();
    });

    input.addEventListener('input', () => {
      selectedIndex = 0;
      renderSearchResults(input.value.trim());
    });

    input.addEventListener('keydown', handleKeyDown);

    voiceBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      toggleVoiceSearch(input);
    });
  }

  // Open Command Palette
  window.openCommandPalette = function (initialQuery = '') {
    injectPaletteDOM();
    const backdrop = document.getElementById('cmdPaletteBackdrop');
    const input = document.getElementById('cmdSearchInput');

    backdrop.classList.add('active');
    document.body.style.overflow = 'hidden';
    isPaletteOpen = true;
    selectedIndex = 0;

    if (input) {
      input.value = initialQuery;
      input.focus();
    }

    renderSearchResults(initialQuery);
  };

  // Close Command Palette
  window.closeCommandPalette = function () {
    const backdrop = document.getElementById('cmdPaletteBackdrop');
    if (backdrop) {
      backdrop.classList.remove('active');
    }
    document.body.style.overflow = '';
    isPaletteOpen = false;
    stopVoiceSearch();
  };

  // Toggle Command Palette
  window.toggleCommandPalette = function () {
    if (isPaletteOpen) {
      closeCommandPalette();
    } else {
      openCommandPalette();
    }
  };

  // Render Search Results
  function renderSearchResults(query = '') {
    const listContainer = document.getElementById('cmdResultsList');
    if (!listContainer) return;

    const lowerQ = query.toLowerCase();
    currentFilteredItems = [];

    // Filter Products from window.productsDB
    const productsDB = window.productsDB || [];
    let matchedProducts = [];

    if (lowerQ) {
      matchedProducts = productsDB.filter(p => 
        (p.title || p.name || '').toLowerCase().includes(lowerQ) ||
        (p.category || '').toLowerCase().includes(lowerQ) ||
        (p.description || '').toLowerCase().includes(lowerQ)
      ).slice(0, 12);
    }

    // Filter Navigation Shortcuts
    const matchedShortcuts = defaultShortcuts.filter(s => 
      !lowerQ || s.title.toLowerCase().includes(lowerQ) || s.badge.toLowerCase().includes(lowerQ)
    );

    // Combine
    if (matchedProducts.length > 0) {
      matchedProducts.forEach(p => {
        currentFilteredItems.push({
          type: 'product',
          title: p.title || p.name,
          category: p.category,
          price: p.price,
          image: p.image,
          description: p.description,
          raw: p
        });
      });
    }

    matchedShortcuts.forEach(s => {
      currentFilteredItems.push(s);
    });

    if (currentFilteredItems.length === 0) {
      listContainer.innerHTML = `
        <div class="cmd-empty-state text-center py-5">
          <i class="fas fa-search-minus fa-2x text-muted mb-2"></i>
          <p class="text-white fw-bold mb-1">No matching products found</p>
          <span class="text-muted fs-xs">Try searching for "Milk", "Atta", "Cart", or "Orders"</span>
        </div>
      `;
      return;
    }

    // Render Items HTML
    let html = '';
    let hasProductHeader = false;
    let hasShortcutHeader = false;

    currentFilteredItems.forEach((item, idx) => {
      const isSelected = idx === selectedIndex;
      const selectedClass = isSelected ? 'selected' : '';

      if (item.type === 'product') {
        if (!hasProductHeader) {
          html += `<div class="cmd-section-label"><i class="fas fa-box me-1"></i> Products</div>`;
          hasProductHeader = true;
        }
        html += `
          <div class="cmd-item ${selectedClass}" data-index="${idx}" onclick="executeCommand(${idx})">
            <div class="cmd-item-img-wrap">
              <img src="${item.image}" alt="${item.title}" onerror="this.src='/static/logo.webp'" />
            </div>
            <div class="cmd-item-info">
              <div class="cmd-item-title">${highlightMatch(item.title, lowerQ)}</div>
              <div class="cmd-item-sub">${item.category} • <span class="text-emerald">Rs. ${item.price}</span></div>
            </div>
            <span class="cmd-item-badge">Quick View</span>
          </div>
        `;
      } else {
        if (!hasShortcutHeader) {
          html += `<div class="cmd-section-label"><i class="fas fa-bolt me-1"></i> Shortcuts & Navigation</div>`;
          hasShortcutHeader = true;
        }
        html += `
          <div class="cmd-item ${selectedClass}" data-index="${idx}" onclick="executeCommand(${idx})">
            <div class="cmd-item-icon">
              <i class="${item.icon}"></i>
            </div>
            <div class="cmd-item-info">
              <div class="cmd-item-title">${highlightMatch(item.title, lowerQ)}</div>
              <div class="cmd-item-sub">Navigation Shortcut</div>
            </div>
            <span class="cmd-item-badge bg-shortcut">${item.badge}</span>
          </div>
        `;
      }
    });

    listContainer.innerHTML = html;

    // Scroll selected into view
    const selectedEl = listContainer.querySelector('.cmd-item.selected');
    if (selectedEl) {
      selectedEl.scrollIntoView({ block: 'nearest' });
    }
  }

  // Highlight query term in string
  function highlightMatch(text, query) {
    if (!query) return text;
    const regex = new RegExp(`(${query})`, 'gi');
    return text.replace(regex, '<mark class="cmd-highlight">$1</mark>');
  }

  // Keyboard navigation handler
  function handleKeyDown(e) {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      if (currentFilteredItems.length > 0) {
        selectedIndex = (selectedIndex + 1) % currentFilteredItems.length;
        renderSearchResults(document.getElementById('cmdSearchInput').value.trim());
      }
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      if (currentFilteredItems.length > 0) {
        selectedIndex = (selectedIndex - 1 + currentFilteredItems.length) % currentFilteredItems.length;
        renderSearchResults(document.getElementById('cmdSearchInput').value.trim());
      }
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (currentFilteredItems.length > 0 && currentFilteredItems[selectedIndex]) {
        executeCommand(selectedIndex);
      }
    } else if (e.key === 'Escape') {
      closeCommandPalette();
    }
  }

  // Execute selected item
  window.executeCommand = function (index) {
    const item = currentFilteredItems[index];
    if (!item) return;

    closeCommandPalette();

    if (item.type === 'product') {
      if (typeof window.showDetails === 'function') {
        window.showDetails(item.title, item.price, item.image, item.category);
      }
    } else if (item.type === 'nav') {
      window.location.href = item.url;
    }
  };

  // Web Speech API Voice Search with explicit mic permission request fallback
  function toggleVoiceSearch(targetInput) {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

    if (!SpeechRecognition) {
      alert('Voice Search requires Google Chrome, Microsoft Edge, or Safari.');
      return;
    }

    if (isListening) {
      stopVoiceSearch();
      return;
    }

    // Attempt microphone stream permission request first if needed
    if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
      navigator.mediaDevices.getUserMedia({ audio: true })
        .then(() => startRecognitionEngine(SpeechRecognition, targetInput))
        .catch(err => {
          console.warn('Microphone permission warning:', err);
          // Try running recognition directly as fallback
          startRecognitionEngine(SpeechRecognition, targetInput);
        });
    } else {
      startRecognitionEngine(SpeechRecognition, targetInput);
    }
  }

  function startRecognitionEngine(SpeechRecognition, targetInput) {
    try {
      if (recognitionInstance) {
        try { recognitionInstance.abort(); } catch (e) {}
      }

      recognitionInstance = new SpeechRecognition();
      recognitionInstance.continuous = false;
      recognitionInstance.interimResults = true;
      recognitionInstance.lang = 'en-US';

      const voiceStatus = document.getElementById('cmdVoiceStatus');
      const voiceMsg = document.getElementById('cmdVoiceMsg');
      const voiceBtn = document.getElementById('cmdVoiceBtn');

      recognitionInstance.onstart = function () {
        isListening = true;
        if (voiceStatus) voiceStatus.style.display = 'flex';
        if (voiceBtn) voiceBtn.classList.add('listening');
        if (voiceMsg) voiceMsg.innerText = 'Listening... Speak now!';
      };

      recognitionInstance.onresult = function (event) {
        let transcript = '';
        for (let i = event.resultIndex; i < event.results.length; i++) {
          transcript += event.results[i][0].transcript;
        }

        if (targetInput) {
          targetInput.value = transcript;
          // Trigger input event to filter catalog on page
          targetInput.dispatchEvent(new Event('input', { bubbles: true }));
          selectedIndex = 0;
          renderSearchResults(transcript);
        }
      };

      recognitionInstance.onerror = function (event) {
        console.warn('Voice Speech Error:', event.error);
        if (voiceMsg) {
          if (event.error === 'not-allowed') {
            voiceMsg.innerText = 'Microphone permission blocked. Please allow mic access in your browser address bar.';
          } else if (event.error === 'no-speech') {
            voiceMsg.innerText = 'No speech detected. Click mic to try again.';
          } else {
            voiceMsg.innerText = `Voice error (${event.error}). Try again.`;
          }
        }
        setTimeout(stopVoiceSearch, 3000);
      };

      recognitionInstance.onend = function () {
        stopVoiceSearch();
      };

      recognitionInstance.start();
    } catch (err) {
      console.error('Speech recognition error:', err);
      stopVoiceSearch();
    }
  }

  function stopVoiceSearch() {
    isListening = false;
    if (recognitionInstance) {
      try { recognitionInstance.stop(); } catch (e) {}
      recognitionInstance = null;
    }
    const voiceStatus = document.getElementById('cmdVoiceStatus');
    const voiceBtn = document.getElementById('cmdVoiceBtn');
    const navVoiceBtns = document.querySelectorAll('.nav-voice-btn');
    if (voiceStatus) voiceStatus.style.display = 'none';
    if (voiceBtn) voiceBtn.classList.remove('listening');
    navVoiceBtns.forEach(btn => btn.classList.remove('listening'));
  }

  // Global Shortcut Listener for Cmd + K / Ctrl + K
  document.addEventListener('keydown', (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
      e.preventDefault();
      toggleCommandPalette();
    }
  });

  // Enhance all existing page search bars on DOM ready
  document.addEventListener('DOMContentLoaded', () => {
    injectPaletteDOM();

    // Attach Voice Search & Cmd+K triggers to navbar search inputs
    const navSearchInputs = document.querySelectorAll('.search-bar input');
    navSearchInputs.forEach(input => {
      const parent = input.parentElement;
      if (parent && !parent.querySelector('.nav-search-tools')) {
        parent.style.position = 'relative';

        // Append KBD badge & Voice button inside navbar search box
        const btnContainer = document.createElement('div');
        btnContainer.className = 'nav-search-tools';
        btnContainer.innerHTML = `
          <button type="button" class="nav-voice-btn" title="Voice Search"><i class="fas fa-microphone"></i></button>
          <span class="nav-kbd-badge" title="Press Cmd+K to open Spotlight Search"><kbd>⌘K</kbd></span>
        `;
        parent.appendChild(btnContainer);

        // Click listeners
        const navVoiceBtn = btnContainer.querySelector('.nav-voice-btn');
        if (navVoiceBtn) {
          navVoiceBtn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            toggleVoiceSearch(input);
          });
        }

        const kbdBadge = btnContainer.querySelector('.nav-kbd-badge');
        if (kbdBadge) {
          kbdBadge.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            openCommandPalette(input.value);
          });
        }
      }
    });
  });

})();
