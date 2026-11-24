async function auditPage(c) {
  setHeader('Audit Logs');
  const d = await api('/api/audit-logs');
  const logs = d.logs || [];
  const actions = [...new Set(logs.map(l => l.action))].sort();
  const actors = [...new Set(logs.map(l => l.actor_name || 'System'))].sort();

  c.innerHTML = `
    <div class="toolbar">
      <input class="input search" id="auditSearch" placeholder="Search action, actor or details…">
      <select class="select" id="auditActionFilter"><option value="">All actions</option>${actions.map(a => `<option value="${esc(a)}">${esc(statusLabel(a))}</option>`).join('')}</select>
      <select class="select" id="auditActorFilter"><option value="">All actors</option>${actors.map(a => `<option value="${esc(a)}">${esc(a)}</option>`).join('')}</select>
    </div>
    <div class="toolbar-meta"><span id="auditCount" class="small muted"></span></div>
    <div class="card" id="auditCard"></div>`;

  const renderRows = () => {
    const q = ($('#auditSearch')?.value || '').toLowerCase();
    const action = $('#auditActionFilter')?.value || '';
    const actor = $('#auditActorFilter')?.value || '';
    const rows = logs.filter(l =>
      (!action || l.action === action) &&
      (!actor || (l.actor_name || 'System') === actor) &&
      (!q || [l.action, l.actor_name || 'System', l.details || ''].join(' ').toLowerCase().includes(q))
    );

    const card = $('#auditCard');
    if (card) {
      card.innerHTML = rows.length
        ? `<div class="table-wrap"><table class="table"><thead><tr><th>When</th><th>Actor</th><th>Action</th><th>Details</th></tr></thead><tbody>${rows.map(l => `
          <tr><td>${fmt(l.created_at)}</td><td>${esc(l.actor_name || 'System')}</td><td>${esc(statusLabel(l.action))}</td><td class="muted">${esc(l.details || '')}</td></tr>`).join('')}</tbody></table></div>`
        : empty('No audit events match these filters.', '<button class="btn small" id="clearAuditFilters">Clear filters</button>');
    }
    const count = $('#auditCount');
    if (count) count.textContent = `${rows.length} event${rows.length === 1 ? '' : 's'}`;

    const clear = $('#clearAuditFilters');
    if (clear) clear.onclick = clearAuditFilters;
  };

  const clearAuditFilters = () => {
    ['auditSearch', 'auditActionFilter', 'auditActorFilter'].forEach(id => {
      const el = $('#' + id);
      if (el) el.value = '';
    });
    renderRows();
  };

  $('#auditSearch').oninput = renderRows;
  $('#auditActionFilter').onchange = renderRows;
  $('#auditActorFilter').onchange = renderRows;
  renderRows();
}
