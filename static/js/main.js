// CCTV Pro — Global JS v2.0
// ─────────────────────────────────────────────────────────

// ── Theme Management ──────────────────────────────────────
(function () {
    const THEME_KEY = 'cctv_theme';

    function getTheme() {
        return localStorage.getItem(THEME_KEY) || document.documentElement.getAttribute('data-theme') || 'light';
    }

    function applyTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem(THEME_KEY, theme);
        
        // Update all theme icons (desktop + mobile)
        const iconClass = theme === 'dark' ? 'fas fa-sun' : 'fas fa-moon';
        document.querySelectorAll('#themeIcon, #mobileThemeIcon').forEach(function (icon) {
            icon.className = iconClass;
        });
    }

    window.toggleTheme = function () {
        const cur = getTheme();
        const next = cur === 'dark' ? 'light' : 'dark';
        applyTheme(next);
    };

    // Apply on load
    document.addEventListener('DOMContentLoaded', function () {
        applyTheme(getTheme());

        // Use global delegated click handler so clicks on button or child icon always work
        document.addEventListener('click', function (e) {
            const btn = e.target.closest('#themeToggleBtn, #mobileThemeToggle');
            if (btn) {
                e.preventDefault();
                window.toggleTheme();
            }
        });
    });
})();

// ── Toast Notifications ───────────────────────────────────
window.showToast = function (message, type = 'info', duration = 4000) {
    const container = document.getElementById('toastContainer');
    if (!container) return;

    const colorMap = { success: 'toast-success', error: 'toast-error', info: 'toast-info' };
    const iconMap  = { success: 'fa-check-circle', error: 'fa-exclamation-circle', info: 'fa-info-circle' };

    const id = 'toast_' + Date.now();
    const div = document.createElement('div');
    div.id = id;
    div.className = `toast ${colorMap[type] || 'toast-info'} show slide-in-right d-flex align-items-center p-3 mb-2`;
    div.style.cssText = 'min-width:260px;max-width:340px;';
    div.innerHTML = `
        <i class="fas ${iconMap[type] || 'fa-info-circle'} me-2"></i>
        <span class="flex-grow-1" style="font-size:.875rem;">${message}</span>
        <button type="button" class="btn-close ms-3" style="filter:invert(1);"
                onclick="document.getElementById('${id}').remove()"></button>
    `;
    container.appendChild(div);
    setTimeout(() => { if (div.parentNode) div.remove(); }, duration);
};

// ── Auto-dismiss Bootstrap alerts ────────────────────────
document.addEventListener('DOMContentLoaded', function () {
    setTimeout(function () {
        document.querySelectorAll('.alert-dismissible').forEach(function (el) {
            try { bootstrap.Alert.getOrCreateInstance(el).close(); } catch (e) {}
        });
    }, 6000);
});

// ── Currency formatter ────────────────────────────────────
window.formatINR = function (val) {
    val = parseFloat(val) || 0;
    return '₹' + val.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
};

// ── Animate elements on scroll (Intersection Observer) ────
document.addEventListener('DOMContentLoaded', function () {
    const cards = document.querySelectorAll('.stat-card, .card, .data-card, .mini-stat-box');
    if (!('IntersectionObserver' in window)) return;

    const obs = new IntersectionObserver(function(entries) {
        entries.forEach(function(e) {
            if (e.isIntersecting) {
                e.target.style.opacity = '1';
                e.target.style.transform = 'translateY(0)';
                obs.unobserve(e.target);
            }
        });
    }, { threshold: 0.1 });

    cards.forEach(function(card) {
        // Only animate if not already transitioned by CSS animation classes
        if (!card.classList.contains('fade-in-up')) {
            card.style.opacity = '0';
            card.style.transform = 'translateY(12px)';
            card.style.transition = 'opacity 0.35s ease, transform 0.35s ease';
            obs.observe(card);
        }
    });
});

// ── Mobile Sidebar & Responsive Viewport Handler ────────────
document.addEventListener('DOMContentLoaded', function () {
    const sidebarEl = document.getElementById('mobileSidebar');

    if (sidebarEl && typeof bootstrap !== 'undefined') {
        // Auto close offcanvas and clean up backdrops when resizing to desktop (>= 992px)
        let resizeTimer;
        window.addEventListener('resize', function () {
            clearTimeout(resizeTimer);
            resizeTimer = setTimeout(function () {
                if (window.innerWidth >= 992) {
                    try {
                        const inst = bootstrap.Offcanvas.getInstance(sidebarEl);
                        if (inst) inst.hide();
                    } catch (err) {}
                    
                    // Clean up any lingering body lock or backdrops
                    document.body.style.overflow = '';
                    document.body.style.paddingRight = '';
                    document.querySelectorAll('.offcanvas-backdrop').forEach(function (b) {
                        b.remove();
                    });
                }
            }, 50);
        });
    }
});
