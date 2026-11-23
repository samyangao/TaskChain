// --- Dashboard ---
async function dashboard(c) {
  setHeader('Dashboard');
  const d = await api('/api/dashboard');
  if (state.user.role === 'requester') return requesterDashboard(c, d);

  const s = d.summary;

  const hour = new Date().getHours();
  const greeting = hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening';
  const firstName = (state.user.full_name || 'there').trim().split(' ')[0];
  const today = new Date().toLocaleDateString([], { weekday: 'long', month: 'long', day: 'numeric' });

  c.innerHTML = `
    <div class="page-intro">
      <div>
        <h2>${greeting}, ${esc(firstName)}</h2>
        <p>${esc(today)} · Here is what needs your attention across the workspace.</p>
      </div>
      <div class="page-intro-actions">
        <button class="btn" id="quickTasks">View my tasks</button>
        <button class="btn primary" id="quickNew">+ New request</button>
      </div>
    </div>
    <div class="grid stats">
      <div class="stat">
        <div class="stat-icon" aria-hidden="true">${ICONS.total}</div>
        <div class="label">Total tasks</div>
        <div class="num">${s.total}</div>
        <div class="sub">Across all categories</div>
      </div>
      <div class="stat">
        <div class="stat-icon" aria-hidden="true">${ICONS.progress}</div>
        <div class="label">In progress</div>
        <div class="num">${s.in_progress}</div>
        <div class="sub">Being worked on now</div>
      </div>
      <div class="stat">
        <div class="stat-icon" aria-hidden="true">${ICONS.verification}</div>
        <div class="label">Verification</div>
        <div class="num">${s.verification}</div>
        <div class="sub">Awaiting sign-off</div>
      </div>
      <div class="stat">
        <div class="stat-icon" aria-hidden="true">${ICONS.done}</div>
        <div class="label">Completed</div>
        <div class="num">${s.completed}</div>
        <div class="sub">Closed and confirmed</div>
      </div>
    </div>
    <div class="grid two">
      <div class="card">
        <div class="card-title"><h3>Recent tasks</h3><button class="btn small" id="allTasks">View all</button></div>
        ${d.recent.length ? taskTable(d.recent) : empty('No tasks yet.')}
      </div>
      <div class="card">
        <div class="card-title"><h3>Task status</h3></div>
        ${statusBars(s)}
      </div>
    </div>
    <div class="card">
      <div class="card-title"><h3>Recent activity</h3><span class="small muted">Latest updates</span></div>
      ${d.recent.length ? `<div class="timeline">${d.recent.slice(0, 5).map(t => `
        <div class="timeline-item">
          <div class="timeline-time">${fmt(t.updated_at)}</div>
          <div class="timeline-body">
            <strong>${esc(t.task_code)} · ${esc(t.title)}</strong>
            <p>${badge(t.status)} ${t.assignee ? `Assigned to ${esc(t.assignee)}` : 'Unassigned'}</p>
          </div>
        </div>`).join('')}</div>` : empty('Activity will appear here.')}
    </div>`;

  $('#allTasks').onclick = () => { state.page = 'tasks'; render(); };
  $('#quickNew').onclick = () => { state.page = 'new'; render(); };
  $('#quickTasks').onclick = () => { state.page = 'tasks'; render(); };
}

// Requester-first dashboard: answer "what do I need to do?" before anything else.
async function requesterDashboard(c, d) {
  const s = d.summary;
  let tasks = [];
  try {
    tasks = (await api('/api/tasks')).tasks || [];
  } catch (_) {
    // Keep the dashboard usable if the detailed list cannot load.
    tasks = [];
  }

  const hour = new Date().getHours();
  const greeting = hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening';
  const firstName = (state.user.full_name || 'there').trim().split(' ')[0];
  const today = new Date().toLocaleDateString([], { weekday: 'long', month: 'long', day: 'numeric' });

  const needsAction = tasks
    .map(t => ({ task: t, action: requesterAction(t) }))
    .filter(x => x.action)
    .sort((a, b) => (a.task.status === 'completed' ? 0 : 1) - (b.task.status === 'completed' ? 0 : 1));

  const active = tasks.length
    ? tasks.filter(t => !['completed', 'cancelled', 'verified'].includes(t.status)).length
    : Math.max(0, s.total - s.completed);

  const recent = (tasks.length ? tasks : d.recent || []).slice(0, 6);
  const reminderHtml = (d.notifications || []).length
    ? d.notifications.map(notifItemHtml).join('')
    : empty('No reminders right now.');

  c.innerHTML = `
    <div class="page-intro">
      <div>
        <h2>${greeting}, ${esc(firstName)}</h2>
        <p>${esc(today)} · Here is what needs your attention in your requests.</p>
      </div>
      <div class="page-intro-actions">
        <button class="btn" id="quickTasks">View my requests</button>
        <button class="btn primary" id="quickNew">＋ New request</button>
      </div>
    </div>

    <div class="grid stats">
      <div class="stat">
        <div class="stat-icon" aria-hidden="true">${ICONS.total}</div>
        <div class="label">Active requests</div>
        <div class="num">${active}</div>
        <div class="sub">Open or in progress</div>
      </div>
      <div class="stat attention">
        <div class="stat-icon" aria-hidden="true">${ICONS.notifications}</div>
        <div class="label">Needs my action</div>
        <div class="num">${needsAction.length}</div>
        <div class="sub">${needsAction.length ? 'Waiting on you' : 'Nothing waiting'}</div>
      </div>
      <div class="stat overdue">
        <div class="stat-icon" aria-hidden="true">${ICONS.sla}</div>
        <div class="label">Overdue</div>
        <div class="num">${s.overdue}</div>
        <div class="sub">Past the expected date</div>
      </div>
      <div class="stat completed">
        <div class="stat-icon" aria-hidden="true">${ICONS.done}</div>
        <div class="label">Completed</div>
        <div class="num">${s.completed}</div>
        <div class="sub">Finished requests</div>
      </div>
    </div>

    <div class="grid two">
      <div>
        <div class="card">
          <div class="card-title">
            <h3>Needs your action</h3>
            <span class="small muted">${needsAction.length ? `${needsAction.length} request${needsAction.length === 1 ? '' : 's'}` : ''}</span>
          </div>
          ${needsAction.length ? `<div class="action-list">${needsAction.map(({ task, action }) => `
            <div class="action-item">
              <div class="action-icon ${action.tone}" aria-hidden="true">${action.icon}</div>
              <div class="action-copy">
                <strong>${esc(task.task_code)} · ${esc(task.title)}</strong>
                <small>${esc(action.detail)}</small>
              </div>
              <button class="btn primary small" data-action-task="${esc(task.id)}">${esc(action.cta)}</button>
            </div>`).join('')}</div>` : empty('Nothing needs your attention right now.')}
        </div>

        <div class="card">
          <div class="card-title"><h3>Recent requests</h3><button class="btn small" id="allTasks">View all</button></div>
          ${recent.length ? taskTable(recent, { requesterView: true }) : empty('No requests yet.', '<button class="btn primary small" id="emptyNew">＋ Create your first request</button>')}
        </div>
      </div>

      <div>
        <div class="card">
          <div class="card-title"><h3>Reminders</h3><span class="small muted">Latest updates</span></div>
          <div id="dashReminders">${reminderHtml}</div>
        </div>

        <div class="card">
          <div class="card-title"><h3>Shortcuts</h3></div>
          <div class="shortcut-list">
            <button class="btn ghost full" id="shortNew">＋ Create new request</button>
            <button class="btn ghost full" id="shortTasks">View my requests</button>
            <button class="btn ghost full" id="shortCalendar">Open calendar</button>
          </div>
        </div>
      </div>
    </div>`;

  $('#quickTasks').onclick = () => { state.page = 'tasks'; render(); };
  $('#quickNew').onclick = () => { state.page = 'new'; render(); };
  $('#shortNew').onclick = () => { state.page = 'new'; render(); };
  $('#shortTasks').onclick = () => { state.page = 'tasks'; render(); };
  $('#shortCalendar').onclick = () => { state.page = 'calendar'; render(); };
  $('#allTasks').onclick = () => { state.page = 'tasks'; render(); };
  if ($('#emptyNew')) $('#emptyNew').onclick = () => { state.page = 'new'; render(); };

  c.querySelectorAll('[data-task]').forEach(el => {
    el.onclick = () => openTask(el.dataset.task);
  });
  c.querySelectorAll('[data-action-task]').forEach(el => {
    el.onclick = () => openTask(el.dataset.actionTask);
  });
  const reminderList = $('#dashReminders');
  if (reminderList) bindNotifList(reminderList);
}

function requesterAction(t) {
  if (t.status === 'completed' && !t.confirmed_at) {
    return {
      tone: 'amber',
      icon: ICONS.done,
      detail: `Completed ${fmt(t.completed_at)}. Confirm the work or reopen the request if it is not finished.`,
      cta: 'Review & confirm'
    };
  }
  if (t.status === 'assigned' && t.assigned_to === state.user.id && !t.accepted_at) {
    return {
      tone: 'blue',
      icon: ICONS.tasks,
      detail: 'This request is assigned to you and is waiting for your acceptance.',
      cta: 'Review assignment'
    };
  }
  return null;
}
