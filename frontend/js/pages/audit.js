async function auditPage(c) {
  setHeader('Audit Logs');
  const d = await api('/api/audit-logs');
  c.innerHTML = `<div class="card"><div class="table-wrap"><table class="table"><thead><tr><th>When</th><th>Actor</th><th>Action</th><th>Details</th></tr></thead><tbody>${
    d.logs.map(l => `<tr><td>${fmt(l.created_at)}</td><td>${esc(l.actor_name || 'System')}</td><td>${esc(statusLabel(l.action))}</td><td class="muted">${esc(l.details || '')}</td></tr>`).join('')}</tbody></table></div></div>`;
}
