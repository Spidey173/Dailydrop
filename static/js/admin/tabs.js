/**
 * Admin Dashboard Tab Navigation Controller
 */
        // Tab Switcher Controller
        function switchAdminTab(tabKey) {
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));

            if (tabKey === 'catalog') {
                document.getElementById('tabBtnCatalog').classList.add('active');
                document.getElementById('tabPaneCatalog').classList.add('active');
                renderPaginatedCatalog();
            } else if (tabKey === 'inquiries') {
                document.getElementById('tabBtnInquiries').classList.add('active');
                document.getElementById('tabPaneInquiries').classList.add('active');
            } else {
                document.getElementById('tabBtnOverview').classList.add('active');
                document.getElementById('tabPaneOverview').classList.add('active');
                // Trigger chart resize when tab switches
                if (window.salesChartInstance) window.salesChartInstance.resize();
                if (window.rfmChartInstance) window.rfmChartInstance.resize();
                if (window.abcChartInstance) window.abcChartInstance.resize();
                if (window.hourlyChartInstance) window.hourlyChartInstance.resize();
            }

            // Sync URL hash
            if (history.replaceState) {
                history.replaceState(null, null, '#' + tabKey);
            }
        }

        // Initialize Tab from URL Hash
