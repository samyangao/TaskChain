// ==========================================
// 5. VIEW ROUTER & PAGES
// ==========================================
let routeTimer = null;

async function render() {
  const bar = $('#routeProgress');
  if (bar) {
    clearTimeout(routeTimer);
    routeTimer = setTimeout(() => bar.classList.add('active'), 120);
  }
  try {
    await renderPage();
    animateStatCounters($('#content'));
  } catch (e) {
    if (e.message === 'Authentication required') return;
    $('#content').innerHTML = `<div class="card"><div class="empty">Error loading page: ${esc(e.message)}</div></div>`;
    toast(e.message);
  } finally {
    if (bar) {
      clearTimeout(routeTimer);
      bar.classList.remove('active');
    }
  }
}

async function renderPage() {
  nav();
  state.allTasksForWorkload = null;
  const c = $('#content');
  
  if (state.page === 'dashboard') return dashboard(c);
  if (state.page === 'tasks') return tasksPage(c);
  if (state.page === 'new') return newRequest(c);
  if (state.page === 'handover') return handoverPage(c);
  if (state.page === 'verification') return verificationPage(c);
  if (state.page === 'notifications') return notificationsPage(c);
  if (state.page === 'calendar') return calendarPage(c);
  if (state.page === 'reports') return reportsPage(c);
  if (state.page === 'users') return usersPage(c);
  if (state.page === 'audit') return auditPage(c);
  if (state.page === 'sla') return slaPage(c);
  if (state.page === 'security') return securityPage(c);
  if (state.page === 'monitor') return monitorPage(c);
}
