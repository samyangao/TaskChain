async function reportsPage(c) {
  setHeader('Reports', 'Insights');
  state.reportFilters = state.reportFilters || {};
  const f = state.reportFilters;
  const qs = new URLSearchParams(Object.entries(f).filter(([, v]) => v)).toString();
  const d = await api('/api/reports' + (qs ? '?' + qs : ''));
  const o = d.filterOptions || {};
  const summary = d.summary || {};
  const statuses = ['submitted', 'under_review', 'assigned', 'accepted', 'in_progress', 'waiting', 'handover', 'overdue', 'for_verification', 'rejected', 'verified', 'completed', 'cancelled'];
  const priorities = ['low', 'medium', 'high', 'urgent'];
  const selected = (value, current) => value === current ? 'selected' : '';
  const bars = (rows, key) => {
    const max = Math.max(1, ...rows.map(r => r.count));
    return `<div class="bar-list">${rows.map(r => `<div class="bar-row"><span>${esc(statusLabel(r[key]))}</span>
      <div class="bar"><i style="width:${Math.round(r.count / max * 100)}%"></i></div><b>${r.count}</b></div>`).join('') || empty('No data.')}</div>`;
  };
  const exportQs = qs ? '?' + qs : '';
  c.innerHTML = `
    <div class="card report-filters">
      <div class="card-title"><h3>Filters</h3><span class="muted small">${esc(d.filters)}</span></div>
      <div class="filter-grid">
        <div class="form-field"><label for="fFrom">From</label><input class="input" id="fFrom" type="date" value="${esc(f.from || '')}"></div>
        <div class="form-field"><label for="fTo">To</label><input class="input" id="fTo" type="date" value="${esc(f.to || '')}"></div>
        <div class="form-field"><label for="fCategory">Category</label><select class="select" id="fCategory"><option value="">All categories</option>${(o.categories || []).map(x => `<option ${selected(x, f.category)}>${esc(x)}</option>`).join('')}</select></div>
        <div class="form-field"><label for="fAssignee">Responsible</label><select class="select" id="fAssignee"><option value="">Anyone</option>${(o.personnel || []).map(x => `<option value="${x.id}" ${selected(x.id, f.assignee)}>${esc(x.full_name)}</option>`).join('')}</select></div>
        <div class="form-field"><label for="fStatus">Status</label><select class="select" id="fStatus"><option value="">Any status</option>${statuses.map(x => `<option value="${x}" ${selected(x, f.status)}>${esc(statusLabel(x))}</option>`).join('')}</select></div>
        <div class="form-field"><label for="fPriority">Priority</label><select class="select" id="fPriority"><option value="">Any priority</option>${priorities.map(x => `<option value="${x}" ${selected(x, f.priority)}>${esc(x)}</option>`).join('')}</select></div>
        <div class="form-field"><label for="fTeam">Team</label><select class="select" id="fTeam"><option value="">Any team</option>${(o.teams || []).map(x => `<option ${selected(x, f.team)}>${esc(x)}</option>`).join('')}</select></div>
        <div class="form-field"><label for="fQ">Search</label><input class="input" id="fQ" value="${esc(f.q || '')}" placeholder="Task code or title"></div>
        <div class="form-field filter-actions">
          <button class="btn primary" id="reportApply">Apply filters</button>
          <button class="btn" id="reportReset">Reset</button>
        </div>
      </div>
      <div class="export-row">
        <span class="muted small">Download this view:</span>
        <a class="btn small" href="/api/reports/export.csv${exportQs}">Export CSV</a>
        <a class="btn small" href="/api/reports/export.pdf${exportQs}">Export PDF</a>
      </div>
    </div>
    <div class="grid stats report-stats">
      <div class="stat"><div class="label">Total tasks</div><div class="num">${summary.total || 0}</div><div class="small muted">In this view</div></div>
      <div class="stat"><div class="label">Active</div><div class="num">${summary.active || 0}</div><div class="small muted">Open and on track</div></div>
      <div class="stat"><div class="label">Completed</div><div class="num">${summary.completed || 0}</div><div class="small muted">Verified or closed</div></div>
      <div class="stat"><div class="label">Overdue</div><div class="num">${summary.overdue || 0}</div><div class="small muted">Past SLA or deadline</div></div>
      <div class="stat"><div class="label">Avg. resolution</div><div class="num">${esc(summary.avg_resolution || '—')}</div><div class="small muted">Request to completion</div></div>
      <div class="stat"><div class="label">SLA compliance</div><div class="num">${esc(summary.sla_compliance || '—')}</div><div class="small muted">Completed within SLA</div></div>
    </div>
    <div class="card">
      <div class="card-title"><h3>Workload split</h3><span class="muted small">Historical = cancelled / archived tasks</span></div>
      ${(d.workload || []).length ? `<div class="table-wrap"><table class="table workload-table">
        <thead><tr><th>Person</th><th>Active</th><th>Completed</th><th>Overdue</th><th>Historical</th><th>Total</th></tr></thead>
        <tbody>${d.workload.map(p => `<tr><td><strong>${esc(p.full_name)}</strong></td>
          <td><span class="badge badge-blue">${p.active}</span></td>
          <td><span class="badge badge-green">${p.completed}</span></td>
          <td><span class="badge badge-red">${p.overdue}</span></td>
          <td><span class="badge badge-gray">${p.historical}</span></td>
          <td><strong>${p.total}</strong></td></tr>`).join('')}</tbody></table></div>`
        : empty('No assigned tasks match these filters.')}
      ${summary.reopened ? `<div class="small muted" style="margin-top:8px">${summary.reopened} task${summary.reopened === 1 ? '' : 's'} reopened at least once in this view.</div>` : ''}
    </div>
    <div class="grid two">
      <div class="card"><div class="card-title"><h3>By status</h3></div>${bars(d.byStatus || [], 'status')}</div>
      <div class="card"><div class="card-title"><h3>By priority</h3></div>${bars(d.byPriority || [], 'priority')}</div>
      <div class="card"><div class="card-title"><h3>By category</h3></div>${bars(d.byCategory || [], 'category')}</div>
      <div class="card"><div class="card-title"><h3>Requester ratings</h3></div>${
        d.ratings.count ? `<div class="rating-average"><span class="rating-number">${d.ratings.average.toFixed(1)}</span> <span class="muted">/ 5 from ${d.ratings.count} rating${d.ratings.count === 1 ? '' : 's'}</span></div>
          <div class="bar-list">${[5, 4, 3, 2, 1].map(n => `<div class="bar-row"><span>${n} ★</span><div class="bar"><i style="width:${Math.round(d.ratings.distribution[n] / d.ratings.count * 100)}%"></i></div><b>${d.ratings.distribution[n]}</b></div>`).join('')}</div>`
        : empty('No ratings yet.')}</div>
      <div class="card"><div class="card-title"><h3>Time in custody per person</h3></div>${
        d.custodyByPerson.length ? `<div class="table-wrap"><table class="table"><thead><tr><th>Person</th><th>Tasks held</th><th>Total time</th></tr></thead><tbody>${
          d.custodyByPerson.map(r => `<tr><td>${esc(r.full_name)}</td><td>${r.tasks}</td><td>${fmtDuration(r.seconds)}</td></tr>`).join('')}</tbody></table></div>`
        : empty('No custody recorded yet.')}</div>
    </div>`;
  const readFilters = () => ({
    from: c.querySelector('#fFrom').value,
    to: c.querySelector('#fTo').value,
    category: c.querySelector('#fCategory').value,
    assignee: c.querySelector('#fAssignee').value,
    status: c.querySelector('#fStatus').value,
    priority: c.querySelector('#fPriority').value,
    team: c.querySelector('#fTeam').value,
    q: c.querySelector('#fQ').value.trim(),
  });
  c.querySelector('#reportApply').onclick = () => {
    const next = readFilters();
    state.reportFilters = Object.fromEntries(Object.entries(next).filter(([, v]) => v));
    render();
  };
  c.querySelector('#reportReset').onclick = () => { state.reportFilters = {}; render(); };
  c.querySelector('#fQ').onkeydown = e => { if (e.key === 'Enter') c.querySelector('#reportApply').click(); };
}
