// ==========================================
// 4. INITIALIZATION & NAVIGATION
// ==========================================
const ICONS = {
  dashboard: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7" rx="1.6"/><rect x="14" y="3" width="7" height="7" rx="1.6"/><rect x="3" y="14" width="7" height="7" rx="1.6"/><rect x="14" y="14" width="7" height="7" rx="1.6"/></svg>',
  tasks: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>',
  new: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><line x1="12" y1="8" x2="12" y2="16"/><line x1="8" y1="12" x2="16" y2="12"/></svg>',
  handover: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M17 2l4 4-4 4"/><path d="M3 11V9a4 4 0 0 1 4-4h14"/><path d="M7 22l-4-4 4-4"/><path d="M21 13v2a4 4 0 0 1-4 4H3"/></svg>',
  verification: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="M9 12l2 2 4-4"/></svg>',
  notifications: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>',
  calendar: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="17" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>',
  reports: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>',
  sla: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><polyline points="12 7 12 12 15 14"/></svg>',
  users: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>',
  audit: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><circle cx="4" cy="6" r="1"/><circle cx="4" cy="12" r="1"/><circle cx="4" cy="18" r="1"/></svg>',
  security: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>',
  monitor: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 3v18h18"/><path d="M7 15l4-6 3 4 4-7"/></svg>',
  total: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2 2 7l10 5 10-5-10-5z"/><path d="m2 17 10 5 10-5"/><path d="m2 12 10 5 10-5"/></svg>',
  progress: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>',
  done: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>'
};

const NAV_ITEMS = [
  ['dashboard', 'Dashboard', 'workspace', false],
  ['tasks', 'My Tasks', 'workspace', false],
  ['new', 'New Request', 'workspace', false],
  ['handover', 'Handover', 'workspace', false],
  ['verification', 'Verification', 'workspace', false],
  ['notifications', 'Notifications', 'workspace', false],
  ['calendar', 'Calendar', 'workspace', false],
  ['security', 'Security', 'workspace', false],
  ['reports', 'Reports', 'manage', false],
  ['sla', 'SLA Settings', 'manage', false],
  ['users', 'Users', 'manage', false],
  ['audit', 'Audit Logs', 'manage', false],
  ['monitor', 'Security Monitor', 'manage', true]
];

async function init() {
  let d;
  try {
    d = await api('/api/me');
  } catch (e) {
    if (e.message === 'Authentication required') return;
    $('#content').innerHTML = `
      <div class="card">
        <div class="card-title"><h3>Can't reach the TaskChain server</h3></div>
        <div class="notice">
          <strong>The page loaded, but the API did not respond.</strong><br>
          <span class="muted">Details: ${esc(e.message)}</span>
        </div>
      </div>`;
    return;
  }
  
  state.user = d.user;
  
  // Setup User UI
  if ($('#sideName')) $('#sideName').textContent = state.user.full_name;
  if ($('#sideRole')) $('#sideRole').textContent = state.user.role;
  if ($('#topName')) $('#topName').textContent = state.user.full_name;
  if ($('#avatar')) $('#avatar').textContent = initials(state.user.full_name);
  if ($('#topAvatar')) $('#topAvatar').textContent = initials(state.user.full_name);
  if ($('#topRole')) $('#topRole').textContent = state.user.role;
  
  nav();
  initTopbar();
  initAccount();
  startNotifPolling();
  startSessionGuard();
  await render();
}

function startSessionGuard() {
  if (window.__sessionGuard) return;
  window.__sessionGuard = setInterval(async () => {
    try {
      const status = await api('/api/session/status');
      if (status.remainingSeconds <= 60 && status.remainingSeconds > 0) {
        toast(`Inactivity sign-out in ${status.remainingSeconds}s.`);
      }
    } catch (_) { /* api() redirects on 401 */ }
  }, 30000);
}

function nav() {
  const canManage = ['administrator', 'coordinator'].includes(state.user.role);
  const visible = NAV_ITEMS.filter(([key, label, group, adminOnly]) => {
    if (adminOnly && state.user.role !== 'administrator') return false;
    if (group === 'manage' && !canManage) return false;
    return true;
  });

  const groups = [['workspace', 'Workspace'], ['manage', 'Insights & Admin']];
  $('#nav').innerHTML = groups.map(([group, label]) => {
    const items = visible.filter(x => x[2] === group);
    if (!items.length) return '';
    return `<div class="nav-section">${label}</div>` + items.map(([key, text]) =>
      `<button class="nav-btn ${state.page === key ? 'active' : ''}" data-page="${key}"${state.page === key ? ' aria-current="page"' : ''}>
        <span class="nav-icon" aria-hidden="true">${ICONS[key] || ''}</span>
        <span>${text}</span>
      </button>`).join('');
  }).join('');

  document.querySelectorAll('.nav-btn').forEach(b => {
    b.onclick = () => {
      state.page = b.dataset.page;
      render();
      closeSidebar();
    };
  });
}

function closeSidebar() {
  const sb = $('#sidebar');
  if (sb) sb.classList.remove('open');
  const scrim = $('#sidebarScrim');
  if (scrim) scrim.classList.remove('show');
  const menu = $('#menuBtn');
  if (menu) menu.setAttribute('aria-expanded', 'false');
}

function setHeader(title, eyebrow = 'Workspace') { 
  if ($('#pageTitle')) $('#pageTitle').textContent = title;
  if ($('#pageEyebrow')) $('#pageEyebrow').textContent = eyebrow;
}

function initAccount() {
  const card = $('#userProfileCard'), chip = $('#topUserChip');
  if (card) card.onclick = accountModal;
  if (chip) {
    chip.onclick = accountModal;
    chip.onkeydown = e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); accountModal(); }};
  }
}

function initTopbar() {
  const notifBtn = $('#notifBtn'), dropdown = $('#notifDropdown');
  if (notifBtn && dropdown) {
    notifBtn.onclick = async (e) => {
      e.stopPropagation();
      const open = dropdown.classList.toggle('show');
      if (open) await loadNotifPreview();
    };
    dropdown.addEventListener('click', e => e.stopPropagation());
    document.addEventListener('click', () => dropdown.classList.remove('show'));
    
    const viewAll = $('#viewAllNotifs');
    if (viewAll) viewAll.onclick = () => { dropdown.classList.remove('show'); state.page = 'notifications'; render(); };
    
    const markAll = $('#markAllReadHeader');
    if (markAll) markAll.onclick = () => markAllRead().catch(e => toast(e.message));
    const quick = $('#notifQuickList');
    if (quick) bindNotifList(quick);
    loadNotifPreview();
  } else if (notifBtn) {
    notifBtn.onclick = () => { state.page = 'notifications'; render(); };
  }
  
  const search = $('#globalSearch');
  if (search) {
    document.addEventListener('keydown', e => {
      const typing = ['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement.tagName);
      if ((e.key === '/' && !typing) || ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k')) {
        e.preventDefault();
        search.focus();
      }
    });
    search.addEventListener('keydown', async e => {
      if (e.key === 'Enter') {
        e.preventDefault();
        const q = search.value.trim();
        state.page = 'tasks';
        await render();
        const taskSearch = $('#taskSearch');
        if (taskSearch) { taskSearch.value = q; filterTasks(); }
      }
    });
  }
}
