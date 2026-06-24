document.addEventListener('DOMContentLoaded', () => {
    // Auto-hide alerts after 5 seconds
    const alerts = document.querySelectorAll('.alert');
    if (alerts.length > 0) {
        setTimeout(() => {
            alerts.forEach(alert => {
                alert.style.transition = 'opacity 0.5s ease, transform 0.5s ease';
                alert.style.opacity = '0';
                alert.style.transform = 'translateY(-10px)';
                setTimeout(() => alert.remove(), 500);
            });
        }, 5000);
    }

    // Dynamic form handling for transactions
    const actionSelect = document.getElementById('action');
    const targetUserGroup = document.getElementById('target-user-group');
    
    if (actionSelect && targetUserGroup) {
        actionSelect.addEventListener('change', (e) => {
            if (e.target.value === 'transfer') {
                targetUserGroup.style.display = 'block';
                document.getElementById('target_username').setAttribute('required', 'required');
            } else {
                targetUserGroup.style.display = 'none';
                document.getElementById('target_username').removeAttribute('required');
            }
        });
    }
});
