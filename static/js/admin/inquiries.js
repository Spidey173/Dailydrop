/**
 * Customer Contact Inquiries Controller
 */
        // ====================================================================
        // CONTACT INQUIRIES HANDLER
        // ====================================================================
        function filterMessages() {
            const query = (document.getElementById('msgSearchInput').value || '').toLowerCase().trim();
            const rows = document.querySelectorAll('#messagesTableBody tr[id^="msg-row-"]');
            rows.forEach(row => {
                const searchData = row.getAttribute('data-search') || '';
                row.style.display = searchData.includes(query) ? '' : 'none';
            });
        }

        async function deleteMessage(messageId, btnEl) {
            if (!confirm(`Are you sure you want to dismiss Inquiry #${messageId}?`)) return;
            try {
                const res = await fetch(`/api/v1/admin/messages/${messageId}/delete`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });
                const data = await res.json();
                if (data.success) {
                    const row = document.getElementById(`msg-row-${messageId}`);
                    if (row) {
                        row.style.transition = 'all 0.3s ease';
                        row.style.opacity = '0';
                        row.style.transform = 'translateX(20px)';
                        setTimeout(() => {
                            row.remove();
                            const remaining = document.querySelectorAll('#messagesTableBody tr[id^="msg-row-"]').length;
                            const badge = document.getElementById('inquiriesBadge');
                            const tableCount = document.getElementById('inquiriesTableCount');
                            if (badge) badge.textContent = remaining;
                            if (tableCount) tableCount.textContent = remaining;
                        }, 300);
                    }
                    showToast(`Inquiry #${messageId} dismissed.`);
                } else {
                    showToast(data.error || 'Failed to dismiss inquiry', true);
                }
            } catch (e) {
                showToast('Server error deleting inquiry', true);
            }
        }

        // Live Time Range Controller for Sales Trajectory Chart
