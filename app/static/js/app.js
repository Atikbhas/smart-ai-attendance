const themeToggle = document.getElementById("themeToggle");
const root = document.documentElement;
const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
const storedTheme = localStorage.getItem("theme") || (prefersDark ? "dark" : "light");

function updateThemeIcon(theme) {
    if (!themeToggle) return;
    const normalizedTheme = theme === "light" ? "light" : "dark";
    themeToggle.innerHTML = normalizedTheme === "dark"
        ? '<i class="bi bi-sun-fill"></i>'
        : '<i class="bi bi-moon-stars-fill"></i>';
}

function applyTheme(theme) {
    const normalizedTheme = theme === "light" ? "light" : "dark";
    root.setAttribute("data-theme", normalizedTheme);
    root.setAttribute("data-bs-theme", normalizedTheme);
    root.style.colorScheme = normalizedTheme;
    updateThemeIcon(normalizedTheme);
}

applyTheme(storedTheme);

if (themeToggle) {
    themeToggle.addEventListener("click", () => {
        const current = root.getAttribute("data-theme") || "dark";
        const next = current === "dark" ? "light" : "dark";
        localStorage.setItem("theme", next);
        applyTheme(next);
    });
}

const sidebar = document.getElementById("sidebar");
const sidebarToggle = document.getElementById("sidebarToggle");
const notificationsToggle = document.getElementById("notificationsToggle");
const notificationsDropdown = document.getElementById("notificationsDropdown");

function applySidebarState(collapsed) {
    if (!sidebar) return;
    sidebar.classList.toggle("collapsed", collapsed);
    const appShell = document.querySelector(".app-shell");
    if (appShell) {
        appShell.classList.toggle("sidebar-collapsed", collapsed);
    }
    if (sidebarToggle) {
        sidebarToggle.setAttribute("aria-expanded", collapsed ? "false" : "true");
    }
}

if (sidebarToggle && sidebar) {
    const savedSidebarState = localStorage.getItem("sidebarCollapsed") === "1";
    applySidebarState(savedSidebarState);
    sidebarToggle.addEventListener("click", (event) => {
        event.preventDefault();
        const collapsed = !sidebar.classList.contains("collapsed");
        applySidebarState(collapsed);
        localStorage.setItem("sidebarCollapsed", collapsed ? "1" : "0");
    });
}

function toggleNotifications() {
    if (!notificationsDropdown || !notificationsToggle) return;
    const isOpen = notificationsDropdown.classList.toggle("show");
    notificationsToggle.setAttribute("aria-expanded", isOpen ? "true" : "false");
}

if (notificationsToggle && notificationsDropdown) {
    notificationsToggle.addEventListener("click", (event) => {
        event.stopPropagation();
        toggleNotifications();
    });

    document.addEventListener("click", (event) => {
        if (!notificationsDropdown.contains(event.target) && !notificationsToggle.contains(event.target)) {
            notificationsDropdown.classList.remove("show");
            notificationsToggle.setAttribute("aria-expanded", "false");
        }
    });
}

function animateCounts() {
    document.querySelectorAll('.count-up').forEach((node) => {
        const value = Number(node.textContent.trim()) || 0;
        let current = 0;
        const step = Math.max(1, Math.round(value / 40));
        const interval = setInterval(() => {
            current += step;
            if (current >= value) {
                node.textContent = value;
                clearInterval(interval);
            } else {
                node.textContent = current;
            }
        }, 15);
    });
}

window.addEventListener('load', animateCounts);

function renderDemoCharts() {
    // All visual charts removed per user request
}

window.renderDemoCharts = renderDemoCharts;

function getCsrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    if (meta && meta.content) return meta.content;
    const input = document.querySelector('input[name="csrf_token"]');
    if (input && input.value) return input.value;
    return '';
}

window.getCsrfToken = getCsrfToken;

async function csrfFetch(url, options = {}) {
    const headers = new Headers(options.headers || {});
    const token = getCsrfToken();
    if (token) {
        headers.set('X-CSRFToken', token);
        headers.set('X-CSRF-Token', token);
    }
    if (!headers.has('Content-Type') && options.body && !(options.body instanceof FormData)) {
        headers.set('Content-Type', 'application/json');
    }
    return fetch(url, { ...options, headers });
}

window.csrfFetch = csrfFetch;
