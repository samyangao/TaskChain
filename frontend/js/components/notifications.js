// --- Notifications (Phase 2a) ---
function setNotifBadge(n) {
  state.notifUnread = n;
  const dot = $('#notifDot'), btn = $('#notifBtn'), sr = $('#notifCount');
  const label = n ? `Notifications, ${n} unread` : 'Notifications';
  if (dot) {
    dot.classList.add('count');
    dot.textContent = n > 99 ? '99+' : String(n);
    dot.style.display = n ? 'flex' : 'none';
  }
  if (sr) sr.textContent = label;
  if (btn) btn.setAttribute('aria-label', label);
}

function notifItemHtml(n) {
  const clickable = n.task_id || !n.is_read;
  return `
    <div class="notif-item rich${n.is_read ? '' : ' unread'}${clickable ? ' clickable' : ''}" data-nid="${esc(n.id)}" data-notif-task="${esc(n.task_id || '')}">
      <div class="notif-main"${n.task_id ? ' role="link" tabindex="0"' : ''}>
        <strong>${esc(n.title)}</strong>${n.task_code ? `<span class="notif-task">${esc(n.task_code)}</span>` : ''}<br>
        <span class="muted">${esc(n.message)}</span><br>
        <span class="muted small">${fmt(n.created_at)}</span>
      </div>
      ${n.is_read ? '' : `<button type="button" class="notif-mark" data-mark="${esc(n.id)}">Mark read</button>`}
    </div>`;
}

async function handleNotifClick(e) {
  try {
    const mark = e.target.closest('[data-mark]');
    if (mark) { e.stopPropagation(); await markNotifRead(mark.dataset.mark); return; }
    const main = e.target.closest('.notif-main');
    if (!main) return;
    const item = main.closest('[data-nid]');
    await openNotification(item.dataset.nid, item.dataset.notifTask, item.classList.contains('unread'));
  } catch (err) { toast(err.message); }
}

function bindNotifList(el) {
  el.onclick = handleNotifClick;
  el.onkeydown = e => {
    if ((e.key === 'Enter' || e.key === ' ') && e.target.classList.contains('notif-main')) {
      e.preventDefault();
      e.target.click();
    }
  };
}

async function markNotifRead(id) {
  const r = await api(`/api/notifications/${id}/read`, { method: 'POST' });
  setNotifBadge(r.unread_count);
  await refreshNotifViews();
}

async function markAllRead() {
  await api('/api/notifications/read', { method: 'POST' });
  setNotifBadge(0);
  await refreshNotifViews();
}

async function openNotification(id, taskId, wasUnread) {
  if (wasUnread) await markNotifRead(id);
  const dd = $('#notifDropdown');
  if (dd) dd.classList.remove('show');
  if (taskId) openTask(taskId);
}

async function loadNotifPreview() {
  const list = $('#notifQuickList');
  if (!list) return;
  try {
    const d = await api('/api/notifications?limit=5');
    setNotifBadge(d.unread_count);
    list.innerHTML = d.notifications.length
      ? d.notifications.map(notifItemHtml).join('')
      : '<div class="empty-notif">No new notifications.</div>';
  } catch (e) {
    list.innerHTML = '<div class="empty-notif">Could not load notifications.</div>';
  }
}

async function refreshNotifViews() {
  await loadNotifPreview();
  if (state.page === 'notifications') await refreshNotifPage();
}

async function refreshNotifPage(c = $('#content')) {
  const d = await api('/api/notifications');
  setNotifBadge(d.unread_count);
  c.innerHTML = `<div class="card">
    <div class="card-title">
      <h3>All notifications ${d.unread_count ? `<span class="badge badge-green">${d.unread_count} unread</span>` : ''}</h3>
      <button class="btn" id="readAll"${d.unread_count ? '' : ' disabled'}>Mark all read</button>
    </div>
    <div id="notifPageList">${d.notifications.length ? d.notifications.map(notifItemHtml).join('') : empty('You are all caught up.')}</div>
  </div>`;
  $('#readAll').onclick = () => markAllRead().catch(e => toast(e.message));
  bindNotifList($('#notifPageList'));
  await renderNotifPrefs(c);
}

// Delivery preferences (Phase 2b). In-app notifications are always on; these only
// add email / Teams / Slack, and are disabled when the server has not configured them.
async function renderNotifPrefs(c) {
  const holder = document.createElement('div');
  holder.className = 'card';
  holder.style.marginTop = '16px';
  holder.id = 'notifPrefs';
  c.appendChild(holder);
  let d;
  try { d = await api('/api/notification-preferences'); }
  catch (e) { holder.innerHTML = `<div class="notice">Could not load delivery preferences: ${esc(e.message)}</div>`; return; }
  const rows = [
    ['email', 'Email', `Send to ${esc(d.email_address)}`],
    ['teams', 'Microsoft Teams', 'Post a short line (title and task code) to the shared Teams channel'],
    ['slack', 'Slack', 'Post a short line (title and task code) to the shared Slack channel']
  ];
  holder.innerHTML = `
    <div class="card-title"><h3>Delivery preferences</h3></div>
    <p class="muted small">In-app notifications are always on. Choose any extra places to receive them.</p>
    ${rows.map(([key, label, hint]) => `
      <label class="pref-row">
        <input type="checkbox" data-pref="${key}" ${d.preferences[key] ? 'checked' : ''} ${d.available[key] ? '' : 'disabled'}>
        <span><strong>${label}</strong><br><span class="muted small">${d.available[key] ? hint : 'Not configured on this server'}</span></span>
      </label>`).join('')}`;
  holder.querySelectorAll('[data-pref]').forEach(box => box.onchange = async () => {
    try {
      const r = await api('/api/notification-preferences', { method: 'PUT', body: JSON.stringify({ [box.dataset.pref]: box.checked }) });
      box.checked = r.preferences[box.dataset.pref];
      toast('Preferences saved.');
    } catch (e) { box.checked = !box.checked; toast(e.message); }
  });
}

// Efficient polling: one tiny request (a count + newest timestamp) every 20 s,
// skipped while the tab is hidden, and run immediately when the tab is shown again.
async function pollNotifications() {
  if (document.hidden || !state.user) return;
  try {
    const d = await api('/api/notifications/unread-count');
    const changed = d.unread_count !== state.notifUnread || d.latest !== state.notifLatest;
    state.notifLatest = d.latest;
    if (!changed) return;
    setNotifBadge(d.unread_count);
    const dd = $('#notifDropdown');
    if (dd && dd.classList.contains('show')) await loadNotifPreview();
    if (state.page === 'notifications') await refreshNotifPage();
  } catch (e) { /* server restarting or offline: try again on the next tick */ }
}

function startNotifPolling() {
  clearInterval(state.notifTimer);
  state.notifTimer = setInterval(pollNotifications, window.TASKCHAIN_POLL_MS || 20000);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) pollNotifications(); });
  pollNotifications();
}
