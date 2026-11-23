/**
 * Customer Audience & Retention Engine Controller
 */
        // ====================================================================
        // CUSTOMER AUDIENCE & RETENTION ENGINE CONTROLLER
        // ====================================================================
        let currentAudienceSegment = 'at_risk';
        let rawAudienceList = [];

        function getAudienceData() {
            if (rawAudienceList.length === 0) {
                try {
                    const el = document.getElementById('customer-audience-json');
                    rawAudienceList = el ? JSON.parse(el.textContent || '[]') : [];
                } catch (e) {
                    rawAudienceList = [];
                }
            }
            return rawAudienceList;
        }

        function updateAudienceBadges() {
            const list = getAudienceData();
            const atRisk = list.filter(c => (c.segment || '').includes('At Risk'));
            const vip = list.filter(c => (c.segment || '').includes('Champions'));
            const loyal = list.filter(c => (c.segment || '').includes('Loyal'));
            const promising = list.filter(c => (c.segment || '').includes('Recent') || (c.segment || '').includes('Promising'));
            const hibernating = list.filter(c => (c.segment || '').includes('Hibernating'));

            const setBadge = (id, count) => {
                const el = document.getElementById(id);
                if (el) el.textContent = count;
            };

            setBadge('badgeCount_at_risk', atRisk.length);
            setBadge('badgeCount_vip', vip.length);
            setBadge('badgeCount_loyal', loyal.length);
            setBadge('badgeCount_promising', promising.length);
            setBadge('badgeCount_hibernating', hibernating.length);
            setBadge('badgeCount_all', list.length);

            const totalBadge = document.getElementById('audienceTotalCountBadge');
            if (totalBadge) totalBadge.textContent = `${list.length} Customers Scored`;

            const playbookCount = document.getElementById('playbookAtRiskCount');
            if (playbookCount) playbookCount.textContent = `${atRisk.length} Top Customers Inactive`;
        }

        function openCustomerAudienceModal(segment = 'at_risk') {
            currentAudienceSegment = segment;
            updateAudienceBadges();

            // Set active tab button
            document.querySelectorAll('.audience-tab-btn').forEach(btn => btn.classList.remove('active'));
            const activeTab = document.getElementById('audTab_' + segment) || document.getElementById('audTab_all');
            if (activeTab) activeTab.classList.add('active');

            // Reset search & city inputs
            const searchInput = document.getElementById('audienceSearchInput');
            if (searchInput) searchInput.value = '';
            const cityFilter = document.getElementById('audienceCityFilter');
            if (cityFilter) cityFilter.value = 'all';

            filterAudienceTable();
            const modal = document.getElementById('customerAudienceModal');
            if (modal) modal.classList.add('active');
        }

        function closeCustomerAudienceModal() {
            const modal = document.getElementById('customerAudienceModal');
            if (modal) modal.classList.remove('active');
        }

        function handleAudienceOverlayClick(e) {
            if (e.target.id === 'customerAudienceModal') {
                closeCustomerAudienceModal();
            }
        }

        function filterAudienceSegment(segment) {
            currentAudienceSegment = segment;
            document.querySelectorAll('.audience-tab-btn').forEach(btn => btn.classList.remove('active'));
            const activeTab = document.getElementById('audTab_' + segment);
            if (activeTab) activeTab.classList.add('active');
            filterAudienceTable();
        }

        function filterAudienceTable() {
            const list = getAudienceData();
            const search = (document.getElementById('audienceSearchInput')?.value || '').toLowerCase().trim();
            const city = document.getElementById('audienceCityFilter')?.value || 'all';

            const filtered = list.filter(c => {
                // Segment match
                let matchSegment = true;
                const seg = c.segment || '';
                if (currentAudienceSegment === 'at_risk') matchSegment = seg.includes('At Risk');
                else if (currentAudienceSegment === 'vip') matchSegment = seg.includes('Champions');
                else if (currentAudienceSegment === 'loyal') matchSegment = seg.includes('Loyal');
                else if (currentAudienceSegment === 'promising') matchSegment = seg.includes('Recent') || seg.includes('Promising');
                else if (currentAudienceSegment === 'hibernating') matchSegment = seg.includes('Hibernating');

                if (!matchSegment) return false;

                // City match
                if (city !== 'all' && (c.city || '').toLowerCase() !== city.toLowerCase()) {
                    return false;
                }

                // Search query match
                if (search) {
                    const text = `${c.name || ''} ${c.email || ''} ${c.phone || ''} ${c.city || ''}`.toLowerCase();
                    if (!text.includes(search)) return false;
                }

                return true;
            });

            renderAudienceTable(filtered);
        }

        function renderAudienceTable(customers) {
            const tbody = document.getElementById('audienceTableBody');
            const countEl = document.getElementById('audienceVisibleCount');
            if (countEl) countEl.textContent = customers.length;
            if (!tbody) return;

            if (customers.length === 0) {
                tbody.innerHTML = `
                    <tr>
                        <td colspan="7" style="text-align: center; padding: 40px; color: var(--text-muted);">
                            <i class="fa-solid fa-user-slash" style="font-size: 2rem; color: rgba(255, 107, 74, 0.3); display: block; margin-bottom: 8px;"></i>
                            No customer profiles found matching this segment and filter criteria.
                        </td>
                    </tr>
                `;
                return;
            }

            let html = '';
            customers.forEach(c => {
                const initials = (c.name || 'CU').split(' ').map(n => n[0]).join('').substring(0, 2).toUpperCase();
                const cleanPhone = (c.phone || '').replace(/[^0-9]/g, '');
                const phoneParam = cleanPhone.length === 10 ? '91' + cleanPhone : cleanPhone;
                const waMsg = encodeURIComponent(`Hi ${c.name}! 👋 We miss you at Daily Drop. Here is ₹150 OFF your next 10-minute grocery delivery with voucher WINBACK150! Shop your favorites here: ${window.location.origin}`);
                const mailSubject = encodeURIComponent(`We miss you at Daily Drop! ₹150 Credit for ${c.name}`);
                const mailBody = encodeURIComponent(`Hi ${c.name},\n\nWe noticed you haven't placed an order recently. We've added ₹150 store credit to your account! Use coupon WINBACK150 at checkout for instant 10-minute delivery.\n\nBest regards,\nDaily Drop Operations Team`);

                let segClass = 'loyal';
                let segLabel = c.segment || 'Loyal Regular';
                if (segLabel.includes('At Risk')) segClass = 'at-risk';
                else if (segLabel.includes('Champions')) segClass = 'vip';
                else if (segLabel.includes('Recent') || segLabel.includes('Promising')) segClass = 'promising';
                else if (segLabel.includes('Hibernating')) segClass = 'hibernating';

                html += `
                    <tr>
                        <td>
                            <div style="display: flex; align-items: center; gap: 10px;">
                                <div class="cust-avatar">${initials}</div>
                                <div>
                                    <strong style="color: #FFFFFF; font-size: 0.88rem; display: block;">${c.name}</strong>
                                    <span style="font-size: 0.72rem; color: var(--text-muted); font-family: 'JetBrains Mono', monospace;">ID: #DD-${c.user_id}</span>
                                </div>
                            </div>
                        </td>
                        <td>
                            <a href="mailto:${c.email}" style="color: var(--accent-peach); text-decoration: none; font-size: 0.8rem; display: block;" title="Email customer">
                                ${c.email}
                            </a>
                            <span style="font-size: 0.75rem; color: var(--text-muted); display: block; margin-top: 2px;">
                                📞 ${c.phone || 'N/A'} • <span class="hub-pill" style="padding: 1px 6px; font-size: 0.68rem;">${c.city || 'Bangalore'}</span>
                            </span>
                        </td>
                        <td style="text-align: right;">
                            <strong style="color: #FF9E7D; font-family: 'JetBrains Mono', monospace; font-size: 0.88rem;">
                                ₹${Number(c.total_spend || 0).toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}
                            </strong>
                            <span style="font-size: 0.72rem; color: var(--text-muted); display: block;">
                                AOV: ₹${Number(c.avg_order_value || 0).toFixed(0)}
                            </span>
                        </td>
                        <td style="text-align: center;">
                            <span class="tab-badge" style="background: rgba(255, 255, 255, 0.06); font-family: 'JetBrains Mono', monospace; padding: 2px 7px;">
                                ${c.total_orders || 0}
                            </span>
                        </td>
                        <td style="text-align: center;">
                            ${c.recency_days >= 21 ? `
                                <span style="display: inline-block; padding: 2px 8px; border-radius: 6px; font-size: 0.72rem; font-weight: 700; background: rgba(244, 63, 94, 0.16); color: #FDA4AF; border: 1px solid rgba(244, 63, 94, 0.3);">
                                    ${c.recency_days}d inactive
                                </span>
                            ` : `
                                <span style="font-size: 0.78rem; color: var(--text-muted);">
                                    ${c.recency_days}d ago
                                </span>
                            `}
                        </td>
                        <td>
                            <span class="cust-segment-pill ${segClass}">
                                ${segClass === 'at-risk' ? '<i class="fa-solid fa-triangle-exclamation"></i>' : ''}
                                ${segClass === 'vip' ? '<i class="fa-solid fa-crown"></i>' : ''}
                                ${c.segment}
                            </span>
                        </td>
                        <td style="text-align: right;">
                            <div style="display: inline-flex; align-items: center; gap: 6px;">
                                <a href="https://wa.me/${phoneParam}?text=${waMsg}" target="_blank" class="btn-nudge-wa" title="Send WhatsApp Win-Back Credit">
                                    <i class="fa-brands fa-whatsapp"></i> Nudge
                                </a>
                                <a href="mailto:${c.email}?subject=${mailSubject}&body=${mailBody}" class="btn-nudge-mail" title="Send Email Offer">
                                    <i class="fa-regular fa-envelope"></i>
                                </a>
                            </div>
                        </td>
                    </tr>
                `;
            });

            tbody.innerHTML = html;
        }

        function exportAudienceCsv() {
            const list = getAudienceData();
            const search = (document.getElementById('audienceSearchInput')?.value || '').toLowerCase().trim();
            const city = document.getElementById('audienceCityFilter')?.value || 'all';

            const filtered = list.filter(c => {
                let matchSegment = true;
                const seg = c.segment || '';
                if (currentAudienceSegment === 'at_risk') matchSegment = seg.includes('At Risk');
                else if (currentAudienceSegment === 'vip') matchSegment = seg.includes('Champions');
                else if (currentAudienceSegment === 'loyal') matchSegment = seg.includes('Loyal');
                else if (currentAudienceSegment === 'promising') matchSegment = seg.includes('Recent') || seg.includes('Promising');
                else if (currentAudienceSegment === 'hibernating') matchSegment = seg.includes('Hibernating');
                if (!matchSegment) return false;
                if (city !== 'all' && (c.city || '').toLowerCase() !== city.toLowerCase()) return false;
                if (search && !`${c.name || ''} ${c.email || ''} ${c.phone || ''} ${c.city || ''}`.toLowerCase().includes(search)) return false;
                return true;
            });

            let csv = 'Customer ID,Name,Email,Phone,City,Total Orders,Total Spend (INR),AOV (INR),Days Inactive,Segment,Last Order Date\n';
            filtered.forEach(c => {
                const clean = (val) => `"${String(val || '').replace(/"/g, '""')}"`;
                csv += [
                    clean(c.user_id),
                    clean(c.name),
                    clean(c.email),
                    clean(c.phone),
                    clean(c.city),
                    c.total_orders || 0,
                    (c.total_spend || 0).toFixed(2),
                    (c.avg_order_value || 0).toFixed(2),
                    c.recency_days || 0,
                    clean(c.segment),
                    clean(c.last_order_str)
                ].join(',') + '\n';
            });

            const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `dailydrop_audience_${currentAudienceSegment}_${new Date().toISOString().slice(0, 10)}.csv`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            showToast(`Exported ${filtered.length} customers to CSV successfully!`);
        }

        function scrollToElement(elementId) {
            const el = document.getElementById(elementId);
            if (el) {
                el.scrollIntoView({ behavior: 'smooth', block: 'center' });
                el.style.transition = 'box-shadow 0.4s ease, border-color 0.4s ease';
                el.style.boxShadow = '0 0 24px rgba(255, 107, 74, 0.45)';
                el.style.borderColor = 'var(--accent-sunset)';
                setTimeout(() => {
                    el.style.boxShadow = '';
                    el.style.borderColor = '';
                }, 2200);
            }
        }
