// --- Dashboard ---
async function dashboard(c) {
  setHeader('Dashboard');
  const d = await api('/api/dashboard');
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
