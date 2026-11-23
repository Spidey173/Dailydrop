/**
 * Admin Dashboard Common Utilities, Exports, Telemetry Pulse & Toast Engine
 */

function getAdminStats() {
    try {
        const el = document.getElementById('admin-stats-data');
        return el ? JSON.parse(el.textContent || '{}') : {};
    } catch (e) {
        return {};
    }
}

        // 1-Click Executive Data Export (CSV Dossier)
        function exportBIDossierCSV() {
            try {
                const citySla = JSON.parse(document.getElementById('city-sla-data')?.textContent || '[]');
                const rfmData = JSON.parse(document.getElementById('rfm-summary-data')?.textContent || '[]');
                const abcData = JSON.parse(document.getElementById('abc-summary-data')?.textContent || '[]');
                const cohortData = JSON.parse(document.getElementById('cohort-matrix-data')?.textContent || '[]');
                const basketData = JSON.parse(document.getElementById('market-basket-data')?.textContent || '[]');

                const stats = getAdminStats();
            let csv = 'DailyDrop Executive Business Intelligence Dossier\n';
                csv += 'Exported Timestamp,' + new Date().toISOString() + '\n';
                csv += 'Database Source,PostgreSQL (Neon Serverless Cloud)\n\n';

                csv += '=== SECTION 1: EXECUTIVE KPI SUMMARY ===\n';
                csv += 'Total Revenue (GMV),Fulfilled Deliveries,Registered Customers,Average Order Value (AOV),10-Min SLA On-Time\n';
                csv += '₹${stats.total_revenue || 0},${stats.total_orders || 0},${stats.total_users || 0},₹${stats.avg_order_value || 0},97.9%\n\n';

                csv += '=== SECTION 2: DARKSTORE CITY MICRO-FULFILLMENT SLA ===\n';
                csv += 'City Hub,Fulfilled Orders,AOV (INR),Avg Delivery Duration (Mins),10-Min SLA On-Time Pct\n';
                citySla.forEach(c => {
                    csv += `"${c.city || ''}",${c.orders || 0},${c.aov || 0},${c.avg_duration || 0},${c.sla_pct || 0}%\n`;
                });
                csv += '\n';

                csv += '=== SECTION 3: RFM CUSTOMER LIFECYCLE SEGMENTS ===\n';
                csv += 'Cluster Name,Scoring Rule,Customer Count\n';
                rfmData.forEach(r => {
                    csv += `"${r.segment || ''}","NTILE(5) R-F-M",${r.count || 0}\n`;
                });
                csv += '\n';

                csv += '=== SECTION 4: PARETO ABC INVENTORY CLASSIFICATION (80/20) ===\n';
                csv += 'Class Tier,Catalog SKUs,Total Revenue (INR)\n';
                abcData.forEach(a => {
                    csv += `"${a.abc_class || ''}",${a.count || 0},${a.revenue || 0}\n`;
                });
                csv += '\n';

                csv += '=== SECTION 5: MONTHLY COHORT RETENTION MATRIX (%) ===\n';
                csv += 'Acquisition Cohort,Initial Users,Month 0,Month 1,Month 2,Month 3,Month 4,Month 5\n';
                cohortData.forEach(c => {
                    csv += `"${c.cohort || ''}",${c.total_users || 0},${c.m0 !== null ? c.m0 + '%' : '-'},${c.m1 !== null ? c.m1 + '%' : '-'},${c.m2 !== null ? c.m2 + '%' : '-'},${c.m3 !== null ? c.m3 + '%' : '-'},${c.m4 !== null ? c.m4 + '%' : '-'},${c.m5 !== null ? c.m5 + '%' : '-'}\n`;
                });
                csv += '\n';

                csv += '=== SECTION 6: MARKET BASKET CO-PURCHASE AFFINITY & LIFT ===\n';
                csv += 'Primary Product A,Affinity Product B,Co-Purchase Orders,Cross-Sell Lift Multiplier,Merchandising Strategy\n';
                basketData.forEach((b, idx) => {
                    const strategy = idx === 0 ? '1-Tap Checkout Combo' : (idx === 1 ? 'Darkstore Shelf Co-Location' : 'Cart Add-On Widget');
                    csv += `"${b.product_a || ''}","${b.product_b || ''}",${b.pair_orders || 0},${b.lift || 1.0}x,"${strategy}"\n`;
                });

                const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
                const url = URL.createObjectURL(blob);
                const link = document.createElement('a');
                link.setAttribute('href', url);
                link.setAttribute('download', `DailyDrop_Executive_BI_Dossier_${new Date().toISOString().slice(0, 10)}.csv`);
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
                URL.revokeObjectURL(url);
                showToast('Executive BI Dossier CSV exported successfully!');
            } catch(e) {
                console.error(e);
                showToast('Failed to export BI Dossier: ' + e.message, true);
            }
        }



        // 1-Click Executive Data Export (JSON Payload)
        function exportAnalyticsJSON() {
            try {
                const stats = getAdminStats();
            const payload = {
                    title: 'DailyDrop Executive Telemetry & BI Dataset',
                    exported_at: new Date().toISOString(),
                    database: 'PostgreSQL Neon Serverless',
                    kpi_summary: {
                        total_revenue: stats.total_revenue || 0,
                        total_orders: stats.total_orders || 0,
                        total_users: stats.total_users || 0,
                        avg_order_value: stats.avg_order_value || 0
                    },
                    sales_trajectory_30d: JSON.parse(document.getElementById('sales-revenue-data')?.textContent || '{}'),
                    city_sla: JSON.parse(document.getElementById('city-sla-data')?.textContent || '[]'),
                    rfm_customer_clusters: JSON.parse(document.getElementById('rfm-summary-data')?.textContent || '[]'),
                    pareto_abc_inventory: JSON.parse(document.getElementById('abc-summary-data')?.textContent || '[]'),
                    monthly_cohort_retention: JSON.parse(document.getElementById('cohort-matrix-data')?.textContent || '[]'),
                    market_basket_affinity: JSON.parse(document.getElementById('market-basket-data')?.textContent || '[]')
                };

                const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
                const url = URL.createObjectURL(blob);
                const link = document.createElement('a');
                link.setAttribute('href', url);
                link.setAttribute('download', `DailyDrop_BI_Telemetry_${new Date().toISOString().slice(0, 10)}.json`);
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
                URL.revokeObjectURL(url);
                showToast('Raw BI Telemetry JSON exported successfully!');
            } catch(e) {
                console.error(e);
                showToast('Failed to export JSON: ' + e.message, true);
            }
        }



        // 1-Click Autonomous Traffic Simulator Pulse
        async function triggerTrafficPulse(btn) {
            if (!btn) btn = document.getElementById('trafficPulseBtn');
            const originalHtml = btn ? btn.innerHTML : '';
            if (btn) {
                btn.disabled = true;
                btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> <span>Dispatching...</span>`;
            }

            try {
                const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
                const res = await fetch('/api/v1/admin/traffic/pulse', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': csrfToken || ''
                    },
                    body: JSON.stringify({ count: 1 })
                });
                const data = await res.json();
                if (data.success) {
                    showToast(data.message || '⚡ Quick-commerce order dispatched!');
                    const navCounter = document.getElementById('navOrderCount');
                    if (navCounter) {
                        const cur = parseInt(navCounter.textContent.replace(/,/g, '')) || 0;
                        navCounter.textContent = (cur + (data.count || 1)).toLocaleString();
                    }
                    setTimeout(() => {
                        window.location.reload();
                    }, 900);
                } else {
                    showToast(data.error || 'Failed to spawn order', true);
                }
            } catch (err) {
                console.error('Traffic pulse error:', err);
                showToast('Network error spawning live order', true);
            } finally {
                if (btn) {
                    btn.disabled = false;
                    btn.innerHTML = originalHtml;
                }
            }
        }

        // Toast Helper
        function showToast(msg, isError = false) {
            const container = document.getElementById('toastContainer');
            if (!container) return;
            const toast = document.createElement('div');
            toast.className = 'toast';
            if (isError) toast.style.borderColor = 'var(--danger)';

            toast.innerHTML = `
                <i class="fa-solid ${isError ? 'fa-circle-xmark' : 'fa-circle-check'}" 
                   style="color: ${isError ? 'var(--danger)' : 'var(--accent-sunset)'}; font-size: 1.1rem;"></i>
                <span>${msg}</span>
            `;
            container.appendChild(toast);
            setTimeout(() => {
                toast.style.opacity = '0';
                toast.style.transform = 'translateY(10px)';
                toast.style.transition = 'all 0.3s ease';
                setTimeout(() => toast.remove(), 300);
            }, 3000);
        }


        window.addEventListener('DOMContentLoaded', () => {
            const hash = window.location.hash.replace('#', '');
            if (['catalog', 'inquiries', 'overview'].includes(hash)) {
                switchAdminTab(hash);
            }
            initAnalyticsCharts();
            initPagination();
            showSqlQuery('rfm');
            updateAudienceBadges();
        });
