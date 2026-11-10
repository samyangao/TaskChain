// ==========================================
// 8. TOPBAR / SIDEBAR CONTROLS + BOOT
// ==========================================
function initChrome() {
  const out = $('#logoutBtn');
  if (out) out.onclick = async () => { try { await api('/api/logout', { method: 'POST' }); } catch {} location.href = '/login.html'; };

  const menu = $('#menuBtn');
  const scrim = $('#sidebarScrim');
  if (menu) menu.onclick = () => {
    const open = $('#sidebar').classList.toggle('open');
    menu.setAttribute('aria-expanded', String(open));
    if (scrim) scrim.classList.toggle('show', open);
  };
  if (scrim) scrim.onclick = closeSidebar;
  document.addEventListener('keydown', e => { if (e.key === 'Escape') closeSidebar(); });

  initTheme();
}

function initTheme() {
  const btn = $('#themeToggleBtn');
  const root = document.documentElement;
  const sun = $('#themeIconLight');
  const moon = $('#themeIconDark');

  const sync = () => {
    const light = root.dataset.theme === 'light';
    if (sun) sun.style.display = light ? 'block' : 'none';
    if (moon) moon.style.display = light ? 'none' : 'block';
    if (btn) btn.setAttribute('aria-pressed', String(light));
  };

  sync();
  if (btn) btn.onclick = () => {
    const next = root.dataset.theme === 'light' ? 'dark' : 'light';
    if (next === 'light') root.dataset.theme = 'light';
    else delete root.dataset.theme;
    try { localStorage.setItem('taskchain-theme', next); } catch (e) {}
    sync();
  };
}

// Boot (this call was missing — it is why the page stayed on "Loading…")
document.addEventListener('DOMContentLoaded', () => { initChrome(); init(); });
