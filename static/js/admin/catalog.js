/**
 * Catalog Table Pagination, Inline Pricing/Stock Editors & Product Modals
 */
        // ====================================================================
        // CLIENT-SIDE TABLE PAGINATION & FILTERING
        // ====================================================================
        let currentPage = 1;
        const pageSize = 25;
        let filteredRows = [];

        function initPagination() {
            filterProducts();
        }

        function filterProducts() {
            const search = (document.getElementById('searchInput').value || '').toLowerCase().trim();
            const category = (document.getElementById('categoryFilter').value || '').toLowerCase().trim();
            const allRows = Array.from(document.querySelectorAll('#productTableBody tr[id^="product-row-"]'));

            filteredRows = allRows.filter(row => {
                const name = (row.getAttribute('data-name') || '').toLowerCase();
                const cat = (row.getAttribute('data-category') || '').toLowerCase();
                const pid = (row.getAttribute('data-product-id') || '').toLowerCase();
                const slider = row.querySelector('.admin-stock-slider');
                const stockVal = parseInt(slider ? slider.value : '999') || 0;

                const matchSearch = !search || name.includes(search) || pid.includes(search);
                const matchCategory = !category || cat === category;
                const matchLowStock = !window.lowStockOnly || stockVal <= 10;

                return matchSearch && matchCategory && matchLowStock;
            });

            currentPage = 1;
            renderPaginatedCatalog();
        }

        function renderPaginatedCatalog() {
            const allRows = document.querySelectorAll('#productTableBody tr[id^="product-row-"]');
            allRows.forEach(r => r.style.display = 'none');

            const total = filteredRows.length;
            const totalPages = Math.max(1, Math.ceil(total / pageSize));
            if (currentPage > totalPages) currentPage = totalPages;
            if (currentPage < 1) currentPage = 1;

            const startIdx = (currentPage - 1) * pageSize;
            const endIdx = Math.min(startIdx + pageSize, total);

            for (let i = startIdx; i < endIdx; i++) {
                filteredRows[i].style.display = '';
                const idxTd = filteredRows[i].querySelector('.row-index');
                if (idxTd) idxTd.textContent = `#${i + 1}`;
            }

            // Update Pagination UI
            const rangeEl = document.getElementById('visibleRange');
            const totalEl = document.getElementById('totalProductsCount');
            const pageInd = document.getElementById('pageIndicator');
            const prevBtn = document.getElementById('prevPageBtn');
            const nextBtn = document.getElementById('nextPageBtn');

            if (rangeEl) rangeEl.textContent = total === 0 ? '0' : `${startIdx + 1} - ${endIdx}`;
            if (totalEl) totalEl.textContent = total;
            if (pageInd) pageInd.textContent = `Page ${currentPage} of ${totalPages}`;
            if (prevBtn) prevBtn.disabled = currentPage <= 1;
            if (nextBtn) nextBtn.disabled = currentPage >= totalPages;
        }

        function changePage(delta) {
            currentPage += delta;
            renderPaginatedCatalog();
            const tableElem = document.querySelector('.product-table');
            if (tableElem) tableElem.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }

        // Low Stock Quick Filter Toggle
        window.lowStockOnly = false;
        function toggleLowStockFilter(btnEl) {
            window.lowStockOnly = !window.lowStockOnly;
            const lowBtn = document.getElementById('lowStockBtn');

            if (window.lowStockOnly) {
                if (lowBtn) {
                    lowBtn.style.background = 'rgba(245, 158, 11, 0.25)';
                    lowBtn.style.borderColor = 'var(--warning)';
                }
                showToast('Filtered catalog to Low Stock items (≤ 10)');
            } else {
                if (lowBtn) {
                    lowBtn.style.background = '';
                    lowBtn.style.borderColor = 'rgba(245, 158, 11, 0.35)';
                }
                showToast('Showing all catalog items');
            }
            filterProducts();
        }

        // ====================================================================
        // INLINE EDITORS & LIVE AJAX HANDLERS
        // ====================================================================
        function enablePriceEdit(container, productId, currentPrice) {
            if (container.querySelector('input') || container.getAttribute('data-saving') === 'true') return;

            const formattedPrice = parseFloat(currentPrice).toFixed(2);
            container.innerHTML = `
                <input type="number" step="0.01" class="price-input" value="${formattedPrice}" 
                       onblur="savePriceEdit(this, ${productId}, ${currentPrice})"
                       onkeydown="if(event.key==='Enter'){ this.removeAttribute('onblur'); savePriceEdit(this, ${productId}, ${currentPrice}); } else if(event.key==='Escape'){ this.removeAttribute('onblur'); cancelPriceEdit(this, ${currentPrice}); }">
            `;
            const input = container.querySelector('input');
            input.focus();
            input.select();
        }

        function cancelPriceEdit(inputOrContainer, oldPrice) {
            const container = inputOrContainer.tagName === 'INPUT' ? inputOrContainer.parentElement : inputOrContainer;
            if (!container) return;
            container.removeAttribute('data-saving');
            const p = parseFloat(oldPrice).toFixed(2);
            container.innerHTML = `<span class="price-value">₹${p}</span> <i class="fa-solid fa-pen price-edit-icon"></i>`;
        }

        async function savePriceEdit(input, productId, oldPrice) {
            const container = input.parentElement;
            if (!container || container.getAttribute('data-saving') === 'true') return;

            const newPrice = parseFloat(input.value);
            if (isNaN(newPrice) || newPrice <= 0) {
                showToast('Please enter a valid price', true);
                cancelPriceEdit(container, oldPrice);
                return;
            }

            if (Math.abs(newPrice - oldPrice) < 0.001) {
                cancelPriceEdit(container, oldPrice);
                return;
            }

            container.setAttribute('data-saving', 'true');
            container.innerHTML = `<i class="fa-solid fa-spinner fa-spin" style="color: var(--accent-sunset);"></i>`;

            try {
                const res = await fetch(`/api/v1/admin/products/${productId}/price`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ price: newPrice })
                });
                const data = await res.json();
                container.removeAttribute('data-saving');

                if (data.success) {
                    container.innerHTML = `<span class="price-value">₹${newPrice.toFixed(2)}</span> <i class="fa-solid fa-pen price-edit-icon"></i>`;
                    container.setAttribute('onclick', `enablePriceEdit(this, ${productId}, ${newPrice})`);
                    const row = document.getElementById(`product-row-${productId}`);
                    if (row) row.setAttribute('data-price', newPrice);
                    showToast(`Updated price to ₹${newPrice.toFixed(2)}!`);
                } else {
                    showToast(data.error || 'Failed to update price', true);
                    cancelPriceEdit(container, oldPrice);
                }
            } catch (err) {
                container.removeAttribute('data-saving');
                showToast('Server error updating price', true);
                cancelPriceEdit(container, oldPrice);
            }
        }

        // Real-Time Stock Slider Handler
        const stockSaveTimers = {};
        function onStockSliderChange(productId, val) {
            val = parseInt(val) || 0;

            const badge = document.getElementById(`stock-badge-${productId}`);
            if (badge) {
                badge.className = 'stock-badge-pill ' + (val < 5 ? 'badge-critical' : (val <= 10 ? 'badge-low' : 'badge-healthy'));
                if (val < 5) {
                    badge.innerHTML = `<i class="fa-solid fa-triangle-exclamation me-1"></i> CRITICAL: ${val}`;
                } else if (val <= 10) {
                    badge.innerHTML = `<i class="fa-solid fa-circle-exclamation me-1"></i> LOW: ${val}`;
                } else {
                    badge.innerHTML = `<i class="fa-solid fa-circle-check me-1"></i> ${val} units`;
                }
            }

            clearTimeout(stockSaveTimers[productId]);
            stockSaveTimers[productId] = setTimeout(() => {
                fetch(`/api/v1/admin/products/${productId}/stock`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ stock: val })
                })
                .then(res => res.json())
                .then(data => {
                    if (data.success) {
                        showToast(`Stock updated for Product #${productId}: ${val} units`);
                    }
                })
                .catch(err => console.error('Error updating stock:', err));
            }, 350);
        }

        // Delete Product
        async function deleteProduct(productId, btnElement) {
            const row = (btnElement && btnElement.closest) ? btnElement.closest('tr') : document.getElementById(`product-row-${productId}`);
            const name = row ? (row.querySelector('strong') ? row.querySelector('strong').textContent : `Product #${productId}`) : `Product #${productId}`;

            if (!confirm(`Are you sure you want to delete "${name}"?`)) return;
            if (btnElement) btnElement.style.opacity = '0.5';

            try {
                const res = await fetch(`/api/v1/admin/products/${productId}/delete`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });
                const data = await res.json();

                if (res.ok && data.success) {
                    if (row) row.remove();
                    showToast(`Deleted "${name}"`);
                    filterProducts();
                } else {
                    if (btnElement) btnElement.style.opacity = '1';
                    showToast(data.error || 'Delete failed', true);
                }
            } catch (err) {
                if (btnElement) btnElement.style.opacity = '1';
                showToast('Error communicating with server', true);
            }
        }

        // ====================================================================
        // MODALS & FORMS
        // ====================================================================
        function openAddModal() {
            document.getElementById('addProductForm').reset();
            const box = document.getElementById('add-image-preview-box');
            if (box) box.style.display = 'none';
            document.getElementById('addModal').classList.add('active');
        }

        function closeAddModal() {
            document.getElementById('addModal').classList.remove('active');
        }

        async function handleAddProduct(e) {
            e.preventDefault();
            const form = e.target;
            const formData = new FormData(form);

            const submitBtn = form.querySelector('button[type="submit"]');
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Saving...`;
            }

            try {
                const res = await fetch('/api/v1/admin/products/add', {
                    method: 'POST',
                    body: formData
                });

                if (res.status === 401) {
                    showToast('Session expired. Redirecting to login...', true);
                    setTimeout(() => window.location.href = '/admin_login', 1500);
                    return;
                }

                const data = await res.json();
                if (res.ok && data.success) {
                    showToast(`Added product "${formData.get('name')}" successfully!`);
                    closeAddModal();
                    setTimeout(() => location.reload(), 700);
                } else {
                    showToast(data.error || 'Failed to add product', true);
                    if (submitBtn) {
                        submitBtn.disabled = false;
                        submitBtn.textContent = 'Save Product';
                    }
                }
            } catch (err) {
                showToast(`Error saving product: ${err.message || err}`, true);
                if (submitBtn) {
                    submitBtn.disabled = false;
                    submitBtn.textContent = 'Save Product';
                }
            }
        }

        function openEditModalFromRow(productId) {
            const row = document.getElementById(`product-row-${productId}`);
            if (!row) return;

            document.getElementById('edit-product-id').value = productId;
            document.getElementById('edit-name').value = row.getAttribute('data-product-name') || '';
            document.getElementById('edit-price').value = row.getAttribute('data-price') || '';
            document.getElementById('edit-category').value = row.getAttribute('data-category') || 'Grocery';
            document.getElementById('edit-subcategory').value = row.getAttribute('data-subcategory') || '';
            document.getElementById('edit-stock').value = row.getAttribute('data-stock') || '50';

            const currentImg = row.getAttribute('data-image') || '/static/product-placeholder.svg';
            document.getElementById('edit-image-preview').src = currentImg;
            document.getElementById('edit-image-file').value = '';

            document.getElementById('editModal').classList.add('active');
        }

        function closeEditModal() {
            document.getElementById('editModal').classList.remove('active');
        }

        async function handleEditProduct(e) {
            e.preventDefault();
            const form = e.target;
            const productId = document.getElementById('edit-product-id').value;
            const formData = new FormData(form);

            const submitBtn = document.getElementById('editSubmitBtn');
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Saving...`;
            }

            try {
                const res = await fetch(`/api/v1/admin/products/${productId}/edit`, {
                    method: 'POST',
                    body: formData
                });

                if (res.status === 401) {
                    showToast('Session expired. Redirecting to login...', true);
                    setTimeout(() => window.location.href = '/admin_login', 1500);
                    return;
                }

                const data = await res.json();
                if (res.ok && data.success) {
                    showToast(`Product #${productId} saved permanently!`);
                    closeEditModal();
                    setTimeout(() => location.reload(), 600);
                } else {
                    showToast(data.error || 'Failed to update product', true);
                    if (submitBtn) {
                        submitBtn.disabled = false;
                        submitBtn.textContent = 'Save Changes';
                    }
                }
            } catch (err) {
                showToast(`Error saving product: ${err.message || err}`, true);
                if (submitBtn) {
                    submitBtn.disabled = false;
                    submitBtn.textContent = 'Save Changes';
                }
            }
        }

        // Live image previews
        document.addEventListener('DOMContentLoaded', () => {
            const addFileInput = document.getElementById('add-image-file');
            if (addFileInput) {
                addFileInput.addEventListener('change', (e) => {
                    const file = e.target.files[0];
                    if (file) {
                        const reader = new FileReader();
                        reader.onload = (evt) => {
                            const preview = document.getElementById('add-image-preview');
                            const box = document.getElementById('add-image-preview-box');
                            if (preview) preview.src = evt.target.result;
                            if (box) box.style.display = 'block';
                        };
                        reader.readAsDataURL(file);
                    }
                });
            }

            const editFileInput = document.getElementById('edit-image-file');
            if (editFileInput) {
                editFileInput.addEventListener('change', (e) => {
                    const file = e.target.files[0];
                    if (file) {
                        const reader = new FileReader();
                        reader.onload = (evt) => {
                            const preview = document.getElementById('edit-image-preview');
                            if (preview) preview.src = evt.target.result;
                        };
                        reader.readAsDataURL(file);
                    }
                });
            }
        });
