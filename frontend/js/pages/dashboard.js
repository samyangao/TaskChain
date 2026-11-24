// --- Dashboard ---
async function dashboard(c) {
  setHeader('Dashboard');
  const d = await api('/api/dashboard');
  if (state.user.role === 'requester') return requesterDashboard(c, d);
  if (state.user.role === 'coordinator') return coordinatorDashboard(c, d);
  if (state.user.role === 'personnel') return personnelDashboard(c, d);
  if (state.user.role === 'verifier') return verifierDashboard(c, d);

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

function dashboardIntro(subtitle, actionsHtml) {
  const hour = new Date().getHours();
  const greeting = hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening';
  const firstName = (state.user.full_name || 'there').trim().split(' ')[0];
  const today = new Date().toLocaleDateString([], { weekday: 'long', month: 'long', day: 'numeric' });
  return `<div class="page-intro">
    <div><h2>${greeting}, ${esc(firstName)}</h2><p>${esc(today)} · ${esc(subtitle)}</p></div>
    <div class="page-intro-actions">${actionsHtml}</div>
  </div>`;
}

function bindDashboardTaskLinks(root) {
  root.querySelectorAll('[data-task]').forEach(el => {
    el.onclick = () => openTask(el.dataset.task);
  });
}

async function coordinatorDashboard(c, d) {
  let tasks = [];
  try { tasks = (await api('/api/tasks')).tasks || []; } catch (_) { tasks = d.recent || []; }

  const active = tasks.filter(t => !['completed', 'cancelled', 'verified'].includes(t.status));
  const unassigned = tasks.filter(t => !t.assigned_to && !['completed', 'cancelled', 'verified'].includes(t.status));
  const overdue = tasks.filter(isTaskOverdue);
  const awaitingVerification = tasks.filter(t => t.status === 'for_verification');

  const workload = {};
  active.filter(t => t.assignee).forEach(t => {
    const name = t.assignee;
    workload[name] = (workload[name] || 0) + 1;
  });
  const workloadRows = Object.entries(workload).sort((a, b) => b[1] - a[1]).slice(0, 6);
  const workloadMax = Math.max(1, ...workloadRows.map(x => x[1]));

  const watch = tasks
    .filter(t => isTaskOverdue(t) || t.sla_state === 'due_soon')
    .sort((a, b) => new Date(a.due_at || 0) - new Date(b.due_at || 0))
    .slice(0, 5);

  c.innerHTML = `
    ${dashboardIntro('Assignments, overdue work and verification queues at a glance.',
      '<button class="btn" id="dashAllTasks">View all requests</button><button class="btn" id="dashReports">Reports</button>')}
    <div class="grid stats">
      <div class="stat attention"><div class="stat-icon" aria-hidden="true">${ICONS.tasks}</div><div class="label">Unassigned</div><div class="num">${unassigned.length}</div><div class="sub">Waiting for personnel</div></div>
      <div class="stat overdue"><div class="stat-icon" aria-hidden="true">${ICONS.sla}</div><div class="label">Overdue</div><div class="num">${overdue.length}</div><div class="sub">Past the expected date</div></div>
      <div class="stat"><div class="stat-icon" aria-hidden="true">${ICONS.verification}</div><div class="label">Awaiting verification</div><div class="num">${awaitingVerification.length}</div><div class="sub">Ready for sign-off</div></div>
      <div class="stat completed"><div class="stat-icon" aria-hidden="true">${ICONS.progress}</div><div class="label">Active work</div><div class="num">${active.length}</div><div class="sub">Open or in progress</div></div>
    </div>
    <div class="grid two">
      <div class="card">
        <div class="card-title"><h3>Needs assignment</h3><span class="small muted">${unassigned.length} waiting</span></div>
        ${unassigned.length ? taskTable(unassigned.slice(0, 5)) : empty('Every open request has an owner.')}
        ${unassigned.length ? '<div class="small muted" style="margin-top:10px">Open a request to assign it to personnel.</div>' : ''}
      </div>
      <div>
        <div class="card">
          <div class="card-title"><h3>Personnel workload</h3></div>
          ${workloadRows.length ? `<div class="bar-list">${workloadRows.map(([name, count]) => `
            <div class="bar-row"><span>${esc(name)}</span><div class="bar"><i style="width:${Math.round(count / workloadMax * 100)}%"></i></div><b>${count}</b></div>`).join('')}</div>` : empty('No active workload yet.')}
        </div>
        <div class="card">
          <div class="card-title"><h3>SLA watch</h3></div>
          ${watch.length ? `<div class="action-list">${watch.map(t => `
            <div class="action-item">
              <div class="action-icon ${isTaskOverdue(t) ? 'red' : 'amber'}" aria-hidden="true">${ICONS.sla}</div>
              <div class="action-copy"><strong>${esc(t.task_code)} · ${esc(t.title)}</strong><small>Due ${fmt(t.due_at)} · ${esc(t.assignee || 'Unassigned')}</small></div>
              <button class="btn small" data-task="${esc(t.id)}">Open</button>
            </div>`).join('')}</div>` : empty('No SLA warnings right now.')}
        </div>
      </div>
    </div>`;

  $('#dashAllTasks').onclick = () => { state.page = 'tasks'; render(); };
  $('#dashReports').onclick = () => { state.page = 'reports'; render(); };
  bindDashboardTaskLinks(c);
}

async function personnelDashboard(c, d) {
  let tasks = [];
  let pendingHandovers = [];
  try {
    const [taskData, handoverData] = await Promise.all([api('/api/tasks'), api('/api/handovers/pending')]);
    tasks = taskData.tasks || [];
    pendingHandovers = handoverData.handovers || [];
  } catch (_) {
    tasks = d.recent || [];
  }

  const mine = tasks.filter(t => t.assigned_to === state.user.id);
  const awaiting = mine.filter(t => ['assigned', 'overdue'].includes(t.status) && !t.accepted_at);
  const active = mine.filter(t => ['accepted', 'in_progress', 'waiting', 'overdue', 'rejected', 'handover'].includes(t.status));
  const weekAhead = Date.now() + 7 * 24 * 3600 * 1000;
  const pendingHandoverIds = new Set(pendingHandovers.map(h => h.task_id));
  const dueSoon = active
    .filter(t => !pendingHandoverIds.has(t.id) && t.due_at && new Date(t.due_at).getTime() <= weekAhead)
    .sort((a, b) => new Date(a.due_at) - new Date(b.due_at));

  const waiting = [
    ...pendingHandovers.map(h => ({ type: 'handover', id: h.task_id, code: h.task_code, title: h.title, detail: `Handover from ${h.from_name} · ${fmt(h.created_at)}` })),
    ...awaiting.map(t => ({ type: 'assignment', id: t.id, code: t.task_code, title: t.title, detail: `Assigned ${fmt(t.updated_at)} · ${t.priority} priority` }))
  ];

  c.innerHTML = `
    ${dashboardIntro('Your assignments, handovers and deadlines in one place.',
      '<button class="btn" id="dashMyTasks">View my tasks</button><button class="btn" id="dashHandover">Handover</button>')}
    <div class="grid stats">
      <div class="stat attention"><div class="stat-icon" aria-hidden="true">${ICONS.tasks}</div><div class="label">Awaiting acceptance</div><div class="num">${awaiting.length}</div><div class="sub">Waiting for your response</div></div>
      <div class="stat"><div class="stat-icon" aria-hidden="true">${ICONS.handover}</div><div class="label">Pending handovers</div><div class="num">${pendingHandovers.length}</div><div class="sub">Need acknowledgment</div></div>
      <div class="stat completed"><div class="stat-icon" aria-hidden="true">${ICONS.progress}</div><div class="label">Active work</div><div class="num">${active.length}</div><div class="sub">Assigned to you</div></div>
      <div class="stat overdue"><div class="stat-icon" aria-hidden="true">${ICONS.sla}</div><div class="label">Due this week</div><div class="num">${dueSoon.length}</div><div class="sub">Including overdue</div></div>
    </div>
    <div class="grid two">
      <div>
        <div class="card">
          <div class="card-title"><h3>Waiting for you</h3><span class="small muted">${waiting.length ? `${waiting.length} item${waiting.length === 1 ? '' : 's'}` : ''}</span></div>
          ${waiting.length ? `<div class="action-list">${waiting.map(x => `
            <div class="action-item">
              <div class="action-icon ${x.type === 'handover' ? 'blue' : 'amber'}" aria-hidden="true">${x.type === 'handover' ? ICONS.handover : ICONS.tasks}</div>
              <div class="action-copy"><strong>${esc(x.code)} · ${esc(x.title)}</strong><small>${esc(x.detail)}</small></div>
              <button class="btn primary small" data-task="${esc(x.id)}">Review</button>
            </div>`).join('')}</div>` : empty('Nothing is waiting for your response.')}
        </div>
        <div class="card">
          <div class="card-title"><h3>Your active work</h3><button class="btn small" id="dashMyTasks2">View all</button></div>
          ${active.length ? taskTable(active.slice(0, 5)) : empty('No active tasks assigned to you.')}
        </div>
      </div>
      <div class="card">
        <div class="card-title"><h3>Upcoming deadlines</h3></div>
        ${dueSoon.length ? `<div class="action-list">${dueSoon.slice(0, 6).map(t => `
          <div class="action-item">
            <div class="action-icon ${isTaskOverdue(t) ? 'red' : 'amber'}" aria-hidden="true">${ICONS.sla}</div>
            <div class="action-copy"><strong>${esc(t.task_code)} · ${esc(t.title)}</strong><small>${fmt(t.due_at)} ${slaChip(t.sla_state)}</small></div>
            <button class="btn small" data-task="${esc(t.id)}">Open</button>
          </div>`).join('')}</div>` : empty('No deadlines in the next seven days.')}
      </div>
    </div>`;

  $('#dashMyTasks').onclick = () => { state.page = 'tasks'; render(); };
  $('#dashMyTasks2').onclick = () => { state.page = 'tasks'; render(); };
  $('#dashHandover').onclick = () => { state.page = 'handover'; render(); };
  bindDashboardTaskLinks(c);
}

async function verifierDashboard(c, d) {
  let tasks = [];
  try { tasks = (await api('/api/verifications')).tasks || []; } catch (_) { tasks = []; }

  const awaiting = tasks.filter(t => t.status === 'for_verification');
  const verified = tasks.filter(t => t.status === 'verified');
  const oldest = awaiting.length
    ? awaiting.reduce((a, b) => new Date(a.updated_at) < new Date(b.updated_at) ? a : b)
    : null;
  const oldestHours = oldest ? Math.max(1, Math.floor((Date.now() - new Date(oldest.updated_at).getTime()) / 3600000)) : null;
  const oldestLabel = oldestHours == null ? '—' : oldestHours >= 24 ? `${Math.floor(oldestHours / 24)}d` : `${oldestHours}h`;

  c.innerHTML = `
    ${dashboardIntro('Completed work waiting for your review and sign-off.',
      '<button class="btn" id="dashQueue">Open verification queue</button><button class="btn" id="dashTasks">View requests</button>')}
    <div class="grid stats">
      <div class="stat attention"><div class="stat-icon" aria-hidden="true">${ICONS.verification}</div><div class="label">Awaiting review</div><div class="num">${awaiting.length}</div><div class="sub">Ready for sign-off</div></div>
      <div class="stat overdue"><div class="stat-icon" aria-hidden="true">${ICONS.sla}</div><div class="label">Oldest waiting</div><div class="num">${esc(oldestLabel)}</div><div class="sub">Longest in queue</div></div>
      <div class="stat completed"><div class="stat-icon" aria-hidden="true">${ICONS.done}</div><div class="label">Verified records</div><div class="num">${verified.length}</div><div class="sub">Marked verified</div></div>
      <div class="stat"><div class="stat-icon" aria-hidden="true">${ICONS.total}</div><div class="label">Queue total</div><div class="num">${tasks.length}</div><div class="sub">Current and recent</div></div>
    </div>
    <div class="grid two">
      <div class="card">
        <div class="card-title"><h3>Review queue</h3><span class="small muted">${awaiting.length} waiting</span></div>
        ${awaiting.length ? `<div class="action-list">${awaiting.slice(0, 5).map(t => `
          <div class="action-item">
            <div class="action-icon amber" aria-hidden="true">${ICONS.verification}</div>
            <div class="action-copy"><strong>${esc(t.task_code)} · ${esc(t.title)}</strong><small>${esc(t.assignee || 'Unassigned')} · completed ${fmt(t.completed_at || t.updated_at)}</small></div>
            <div class="action-actions">
              <button class="btn small" data-review="${esc(t.id)}">Review evidence</button>
              <button class="btn primary small" data-verdict="approve" data-id="${esc(t.id)}">Approve</button>
              <button class="btn danger small" data-verdict="reject" data-id="${esc(t.id)}">Reject…</button>
            </div>
          </div>`).join('')}</div>` : empty('Nothing is waiting for verification.')}
      </div>
      <div class="card">
        <div class="card-title"><h3>Recently verified</h3><button class="btn small" id="dashQueue2">View all</button></div>
        ${verified.length ? taskTable(verified.slice(0, 5)) : empty('Approved requests move to Completed and leave this queue.')}
      </div>
    </div>`;

  $('#dashQueue').onclick = () => { state.page = 'verification'; render(); };
  $('#dashQueue2').onclick = () => { state.page = 'verification'; render(); };
  $('#dashTasks').onclick = () => { state.page = 'tasks'; render(); };
  c.querySelectorAll('[data-review]').forEach(el => {
    el.onclick = () => openTask(el.dataset.review, 'evidence');
  });
  c.querySelectorAll('[data-verdict]').forEach(el => {
    el.onclick = () => {
      const task = awaiting.find(x => x.id === el.dataset.id);
      if (task) verificationDecisionModal(task, el.dataset.verdict, () => render());
    };
  });
  bindDashboardTaskLinks(c);
}
