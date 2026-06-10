<!-- Shared sidebar HTML snippet — included via JS in app pages -->
<!-- Usage: call renderSidebar('active-page-id') from each app page -->
<script>
/**
 * Renders the application sidebar into #sidebar-mount.
 * @param {string} activePage - 'dashboard' | 'upload' | 'evaluator' | 'reports' | 'settings'
 */
function renderSidebar(activePage) {
  const nav = [
    { id: 'dashboard', label: 'Dashboard',  icon: 'dashboard',    href: 'dashboard.html'  },
    { id: 'upload',    label: 'Processing', icon: 'cloud_upload',  href: 'upload.html'     },
    { id: 'evaluator', label: 'Evaluator',  icon: 'visibility',   href: 'evaluator.html'  },
    { id: 'reports',   label: 'Reports',    icon: 'description',  href: 'reports.html'    },
    { id: 'settings',  label: 'Settings',   icon: 'settings',     href: 'settings.html'   },
  ];

  const navHtml = nav.map(({ id, label, icon, href }) => `
    <a href="${href}" class="${activePage === id ? 'active' : ''}">
      <span class="material-symbols-outlined"${activePage === id ? " style=\"font-variation-settings:'FILL' 1;\"" : ''}>${icon}</span>
      ${label}
    </a>
  `).join('');

  const sidebar = document.getElementById('sidebar-mount');
  if (!sidebar) return;

  sidebar.innerHTML = `
    <div class="sidebar-brand">
      <div class="sidebar-brand-icon">
        <span class="material-symbols-outlined" style="font-variation-settings:'FILL' 1;font-size:1.125rem;">school</span>
      </div>
      <div class="sidebar-brand-text">
        <h1>GRADE</h1>
        <p>Institutional Portal</p>
      </div>
    </div>
    <div style="padding:0 1rem 0.75rem;">
      <button class="sidebar-new-btn" onclick="window.location='upload.html'">
        <span class="material-symbols-outlined" style="font-size:1rem;">add_circle</span>
        New Evaluation
      </button>
    </div>
    <nav class="sidebar-nav">${navHtml}</nav>
    <div class="sidebar-footer">
      <a href="#">
        <span class="material-symbols-outlined" style="font-size:1.125rem;">help</span>
        Help Center
      </a>
      <a href="#">
        <span class="material-symbols-outlined" style="font-size:1.125rem;">account_circle</span>
        Account
      </a>
    </div>
  `;
}

/**
 * Renders the app topbar into #topbar-mount.
 * @param {string} title - Page title to display.
 * @param {boolean} showStatus - Whether to show the system active badge.
 */
function renderTopbar(title, showStatus = true) {
  const mount = document.getElementById('topbar-mount');
  if (!mount) return;

  mount.innerHTML = `
    <div class="topbar-title">
      <h2>${title}</h2>
      ${showStatus ? `
      <div class="status-badge">
        <div class="status-dot"></div>
        <span>System Active</span>
      </div>` : ''}
    </div>
    <div class="topbar-actions">
      <div class="topbar-search">
        <span class="material-symbols-outlined">search</span>
        <input type="text" placeholder="Search papers, students…" id="global-search" aria-label="Global search"/>
      </div>
      <button class="icon-btn" title="Notifications" aria-label="Notifications">
        <span class="material-symbols-outlined">notifications</span>
        <div class="notif-badge"></div>
      </button>
      <div class="avatar" title="Account">MD</div>
    </div>
  `;
}

/**
 * Fetches data from the GRADE FastAPI backend.
 * Falls back to mock data if the server is unreachable.
 */
const API_BASE = 'http://localhost:8000';

async function apiFetch(endpoint, options = {}) {
  try {
    const res = await fetch(`${API_BASE}${endpoint}`, {
      headers: { 'Content-Type': 'application/json' },
      ...options,
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    console.warn(`[GRADE] API unavailable (${endpoint}):`, err.message);
    return null;
  }
}

/** Returns true if the API is reachable */
async function checkApiHealth() {
  try {
    const r = await fetch(`${API_BASE}/health`, { signal: AbortSignal.timeout(2000) });
    return r.ok;
  } catch {
    return false;
  }
}
</script>
