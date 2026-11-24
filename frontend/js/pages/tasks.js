// --- Tasks ---
async function tasksPage(c) {
  setHeader(navLabel('tasks'));
  const d = await api('/api/tasks');
  state.tasks = d.tasks;

  c.innerHTML = `
    <div class="toolbar">
      <input class="input search" id="taskSearch" placeholder="Search request ID, title, requester or handler…">
      <select class="select" id="statusFilter">
        <option value="">All statuses</option>
        ${['submitted','under_review','assigned','accepted','in_progress','waiting','handover','for_verification','completed','rejected','cancelled','overdue'].map(s => `<option value="${s}">${statusLabel(s)}</option>`).join('')}
      </select>
      <select class="select" id="priorityFilter">
        <option value="">Any priority</option>
        ${['urgent','high','medium','low'].map(p => `<option value="${p}">${p[0].toUpperCase() + p.slice(1)}</option>`).join('')}
      </select>
      <select class="select" id="sortTasks">
        <option value="updated_desc">Recently updated</option>
        <option value="due_asc">Due soonest</option>
        <option value="priority_desc">Highest priority</option>
      </select>
      <label class="toolbar-check"><input type="checkbox" id="overdueOnly"> Overdue only</label>
      <button class="btn primary" id="newBtn">＋ New request</button>
    </div>
    <div class="toolbar-meta"><span id="taskCount" class="small muted"></span></div>
    <div class="card" id="taskCard"></div>`;

  $('#taskSearch').oninput = filterTasks;
  $('#statusFilter').onchange = filterTasks;
  $('#priorityFilter').onchange = filterTasks;
  $('#sortTasks').onchange = filterTasks;
  $('#overdueOnly').onchange = filterTasks;
  $('#newBtn').onclick = () => { state.page = 'new'; render(); };
  filterTasks();
}

function isTaskOverdue(t) {
  if (t.status === 'overdue') return true;
  if (['completed', 'cancelled', 'verified'].includes(t.status)) return false;
  return !!(t.due_at && new Date(t.due_at).getTime() < Date.now());
}

function filterTasks() {
  const q = ($('#taskSearch')?.value || '').toLowerCase();
  const status = $('#statusFilter')?.value || '';
  const priority = $('#priorityFilter')?.value || '';
  const overdueOnly = !!$('#overdueOnly')?.checked;
  const sort = $('#sortTasks')?.value || 'updated_desc';
  const priorityRank = { urgent: 4, high: 3, medium: 2, low: 1 };

  let rows = state.tasks.filter(t =>
    (!status || t.status === status) &&
    (!priority || t.priority === priority) &&
    (!overdueOnly || isTaskOverdue(t)) &&
    (!q || [t.task_code, t.title, t.requester, t.assignee].join(' ').toLowerCase().includes(q))
  );

  rows = rows.slice().sort((a, b) => {
    if (sort === 'due_asc') {
      const aDue = a.due_at ? new Date(a.due_at).getTime() : Infinity;
      const bDue = b.due_at ? new Date(b.due_at).getTime() : Infinity;
      return aDue - bDue;
    }
    if (sort === 'priority_desc') {
      return (priorityRank[b.priority] || 0) - (priorityRank[a.priority] || 0);
    }
    return new Date(b.updated_at || 0) - new Date(a.updated_at || 0);
  });

  const card = $('#taskCard');
  if (card) {
    card.innerHTML = rows.length
      ? taskTable(rows)
      : empty('No requests match these filters.', '<button class="btn small" id="clearTaskFilters">Clear filters</button>');
  }
  const count = $('#taskCount');
  if (count) count.textContent = `${rows.length} request${rows.length === 1 ? '' : 's'}`;

  const clear = $('#clearTaskFilters');
  if (clear) clear.onclick = clearTaskFilters;
  document.querySelectorAll('[data-task]').forEach(x => x.onclick = () => openTask(x.dataset.task));
}

function clearTaskFilters() {
  ['taskSearch', 'statusFilter', 'priorityFilter'].forEach(id => {
    const el = $('#' + id);
    if (el) el.value = '';
  });
  const overdue = $('#overdueOnly');
  if (overdue) overdue.checked = false;
  const sort = $('#sortTasks');
  if (sort) sort.value = 'updated_desc';
  filterTasks();
}
