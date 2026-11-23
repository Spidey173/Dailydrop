/**
 * Admin Dashboard Chart.js Controllers & Visualization Engine
 */
        // ====================================================================
        // CHART.JS CONTROLLERS (SHOWCASE GRADE)
        // ====================================================================
        let salesChartInstance = null;
        let rfmChartInstance = null;
        let abcChartInstance = null;
        let hourlyChartInstance = null;

        function initAnalyticsCharts() {
            if (typeof Chart === 'undefined') return;

            // Global Chart Defaults for Sunset Twilight Dark Mode
            Chart.defaults.color = '#8E8EA8';
            Chart.defaults.font.family = "'Plus Jakarta Sans', sans-serif";

            // 1. Hero 30-Day Sales Velocity Area Chart
            const salesCanvas = document.getElementById('salesRevenueChart');
            if (salesCanvas) {
                const salesDataEl = document.getElementById('sales-revenue-data');
                const salesInfo = salesDataEl ? JSON.parse(salesDataEl.textContent || '{}') : {};
                window._rawSalesInfo = salesInfo;
                const labels = salesInfo.labels || [];
                const values = salesInfo.data || [];

                const formattedLabels = labels.map(d => {
                    try {
                        const parts = d.split('-');
                        const dt = new Date(parts[0], parts[1] - 1, parts[2]);
                        return dt.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
                    } catch(e) { return d; }
                });

                const ctx = salesCanvas.getContext('2d');
                const gradient = ctx.createLinearGradient(0, 0, 0, 260);
                gradient.addColorStop(0, 'rgba(255, 107, 74, 0.45)');
                gradient.addColorStop(0.65, 'rgba(244, 63, 94, 0.12)');
                gradient.addColorStop(1, 'rgba(255, 107, 74, 0.0)');

                window.salesChartInstance = new Chart(salesCanvas, {
                    type: 'line',
                    data: {
                        labels: formattedLabels,
                        datasets: [{
                            label: 'Daily Revenue (₹)',
                            data: values,
                            borderColor: '#FF6B4A',
                            borderWidth: 2.5,
                            backgroundColor: gradient,
                            fill: true,
                            tension: 0.38,
                            pointBackgroundColor: '#FDBA74',
                            pointBorderColor: '#0B0A14',
                            pointBorderWidth: 1.5,
                            pointRadius: 3,
                            pointHoverRadius: 6
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        interaction: { intersect: false, mode: 'index' },
                        plugins: {
                            legend: { display: false },
                            tooltip: {
                                backgroundColor: '#131224',
                                titleColor: '#FFFFFF',
                                bodyColor: '#FF9E7D',
                                borderColor: 'rgba(255, 107, 74, 0.3)',
                                borderWidth: 1,
                                padding: 12,
                                displayColors: false,
                                callbacks: {
                                    label: (ctx) => `Daily Revenue: ₹${parseFloat(ctx.parsed.y).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`
                                }
                            }
                        },
                        scales: {
                            x: {
                                grid: { color: 'rgba(255, 255, 255, 0.04)' },
                                ticks: { font: { size: 10 }, color: '#8E8EA8', maxRotation: 0, autoSkip: true, maxTicksLimit: 12 }
                            },
                            y: {
                                grid: { color: 'rgba(255, 255, 255, 0.05)' },
                                ticks: {
                                    font: { size: 10 },
                                    color: '#8E8EA8',
                                    callback: (val) => '₹' + (val >= 1000 ? (val / 1000) + 'k' : val)
                                }
                            }
                        }
                    }
                });
            }

            // 2. Customer RFM Segmentation Doughnut Chart
            const rfmCanvas = document.getElementById('rfmSegmentsChart');
            if (rfmCanvas) {
                const rfmDataEl = document.getElementById('rfm-summary-data');
                const rfmList = rfmDataEl ? JSON.parse(rfmDataEl.textContent || '[]') : [];
                
                const labels = rfmList.length > 0 ? rfmList.map(r => r.segment) : ['Champions (VIP)', 'Loyal Regulars', 'At Risk', 'Hibernating', 'Recent'];
                const values = rfmList.length > 0 ? rfmList.map(r => r.count) : [35, 68, 47, 54, 38];

                window.rfmChartInstance = new Chart(rfmCanvas, {
                    type: 'doughnut',
                    data: {
                        labels: labels,
                        datasets: [{
                            data: values,
                            backgroundColor: ['#FF6B4A', '#FBBF24', '#F43F5E', '#8B5CF6', '#EC4899', '#FB923C'],
                            borderColor: '#131224',
                            borderWidth: 2,
                            hoverOffset: 4
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        cutout: '72%',
                        layout: {
                            padding: 8
                        },
                        plugins: {
                            legend: { display: false },
                            tooltip: {
                                backgroundColor: '#131224',
                                titleColor: '#FFFFFF',
                                bodyColor: '#FF9E7D',
                                borderColor: 'rgba(255, 107, 74, 0.3)',
                                borderWidth: 1,
                                padding: 10,
                                callbacks: {
                                    label: (ctx) => ` ${ctx.label}: ${ctx.raw} customers`
                                }
                            }
                        }
                    }
                });
            }

            // 3. Pareto ABC Inventory Doughnut Chart
            const abcCanvas = document.getElementById('abcInventoryChart');
            if (abcCanvas) {
                const abcDataEl = document.getElementById('abc-summary-data');
                const abcList = abcDataEl ? JSON.parse(abcDataEl.textContent || '[]') : [];

                const labels = abcList.length > 0 ? abcList.map(a => a.abc_class) : ['Class A (80% GMV)', 'Class B (15% GMV)', 'Class C (5% GMV)'];
                const values = abcList.length > 0 ? abcList.map(a => parseFloat(a.revenue)) : [1270725, 241594, 81485];

                window.abcChartInstance = new Chart(abcCanvas, {
                    type: 'doughnut',
                    data: {
                        labels: labels,
                        datasets: [{
                            data: values,
                            backgroundColor: ['#FF6B4A', '#FBBF24', '#8B5CF6'],
                            borderColor: '#131224',
                            borderWidth: 2,
                            hoverOffset: 4
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        cutout: '72%',
                        layout: {
                            padding: 8
                        },
                        plugins: {
                            legend: { display: false },
                            tooltip: {
                                backgroundColor: '#131224',
                                titleColor: '#FFFFFF',
                                bodyColor: '#FF9E7D',
                                borderColor: 'rgba(255, 107, 74, 0.3)',
                                borderWidth: 1,
                                padding: 10,
                                callbacks: {
                                    label: (ctx) => ` ${ctx.label}: ₹${parseFloat(ctx.raw).toLocaleString('en-IN', { minimumFractionDigits: 0 })}`
                                }
                            }
                        }
                    }
                });
            }

            // 4. Peak Demand 24-Hour Bar Chart
            const hourlyCanvas = document.getElementById('hourlyOrdersChart');
            if (hourlyCanvas) {
                const hourlyDataEl = document.getElementById('hourly-distribution-data');
                const hourlyData = hourlyDataEl ? JSON.parse(hourlyDataEl.textContent || '{}') : {};
                const labels = Object.keys(hourlyData);
                const values = Object.values(hourlyData);

                const colors = labels.map(h => {
                    const hourInt = parseInt(h.split(':')[0]) || 0;
                    if ((hourInt >= 8 && hourInt <= 10) || (hourInt >= 18 && hourInt <= 21)) {
                        return 'rgba(255, 107, 74, 0.90)';
                    }
                    return 'rgba(139, 92, 246, 0.35)';
                });

                window.hourlyChartInstance = new Chart(hourlyCanvas, {
                    type: 'bar',
                    data: {
                        labels: labels,
                        datasets: [{
                            label: 'Orders',
                            data: values,
                            backgroundColor: colors,
                            borderRadius: 4,
                            borderSkipped: false
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: { display: false },
                            tooltip: {
                                backgroundColor: '#131224',
                                titleColor: '#FFFFFF',
                                bodyColor: '#FF9E7D',
                                borderColor: 'rgba(255, 107, 74, 0.3)',
                                borderWidth: 1,
                                padding: 10,
                                callbacks: {
                                    label: (ctx) => ` Volume: ${ctx.parsed.y} orders placed`
                                }
                            }
                        },
                        scales: {
                            x: {
                                grid: { display: false },
                                ticks: { font: { size: 8 }, color: '#8E8EA8' }
                            },
                            y: {
                                grid: { color: 'rgba(255, 255, 255, 0.05)' },
                                ticks: { font: { size: 9 }, color: '#8E8EA8', precision: 0 }
                            }
                        }
                    }
                });
            }
        }



        function setChartTimeRange(days, btnElement) {
            if (!window.salesChartInstance) return;
            document.querySelectorAll('.time-toggle-btn').forEach(b => b.classList.remove('active'));
            if (btnElement) btnElement.classList.add('active');

            const salesDataEl = document.getElementById('sales-revenue-data');
            const salesInfo = window._rawSalesInfo || (salesDataEl ? JSON.parse(salesDataEl.textContent || '{}') : {});
            const rawLabels = salesInfo.labels || [];
            const rawValues = salesInfo.data || [];

            const slicedLabels = rawLabels.slice(-days);
            const slicedValues = rawValues.slice(-days);

            const formattedLabels = slicedLabels.map(d => {
                try {
                    const parts = d.split('-');
                    const dt = new Date(parts[0], parts[1] - 1, parts[2]);
                    return dt.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
                } catch(e) { return d; }
            });

            const rangeTotal = slicedValues.reduce((a, b) => a + Number(b || 0), 0);
            const rangeAvg = slicedValues.length > 0 ? (rangeTotal / slicedValues.length) : 0;

            window.salesChartInstance.data.labels = formattedLabels;
            window.salesChartInstance.data.datasets[0].data = slicedValues;
            window.salesChartInstance.update();

            const pill = document.getElementById('salesRangePill');
            if (pill) {
                pill.innerHTML = `<i class="fa-solid fa-circle-dot"></i> Live ${days}D GMV: ₹${rangeTotal.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} (Avg: ₹${rangeAvg.toLocaleString('en-IN', { maximumFractionDigits: 0 })}/day)`;
            }
        }
