// --- Tasks ---
async function tasksPage(c) {
  setHeader('Tasks');
  const d = await api('/api/tasks');
  state.tasks = d.tasks;
  
  c.innerHTML = `
    <div class="toolbar">
      <input class="input search" id="taskSearch" placeholder="Search task ID, title...">
      <select class="select" id="statusFilter">
        <option value="">All statuses</option>
        ${['submitted','under_review','assigned','accepted','in_progress','waiting','handover','for_verification','completed','rejected','cancelled','overdue'].map(s => `<option value="${s}">${statusLabel(s)}</option>`).join('')}
      </select>
      <button class="btn primary" id="newBtn">＋ New request</button>
    </div>
    <div class="card" id="taskCard">${taskTable(d.tasks)}</div>`;
    
  $('#taskSearch').oninput = filterTasks;
  $('#statusFilter').onchange = filterTasks;
  $('#newBtn').onclick = () => { state.page = 'new'; render(); };
  document.querySelectorAll('[data-task]').forEach(x => x.onclick = () => openTask(x.dataset.task));
}

function filterTasks() {
  const q = $('#taskSearch').value.toLowerCase(), s = $('#statusFilter').value;
  const rows = state.tasks.filter(t => 
    (!s || t.status === s) && 
    (!q || [t.task_code, t.title, t.requester, t.assignee].join(' ').toLowerCase().includes(q))
  );
  $('#taskCard').innerHTML = taskTable(rows);
  document.querySelectorAll('[data-task]').forEach(x => x.onclick = () => openTask(x.dataset.task));
}
