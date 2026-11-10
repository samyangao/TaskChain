async function verificationPage(c) {
  setHeader('Verification');
  if (!['administrator', 'coordinator', 'verifier'].includes(state.user.role)) {
    c.innerHTML = `<div class="card">${empty('Only verifiers can review completed work.')}</div>`; return;
  }
  const d = await api('/api/verifications');
  c.innerHTML = `<div class="card"><div class="card-title"><h3>Awaiting verification</h3></div>${
    d.tasks.length ? `<div class="table-wrap"><table class="table"><thead><tr><th>Task</th><th>Responsible</th><th>Status</th><th></th></tr></thead><tbody>${
      d.tasks.map(t => `<tr><td><strong>${esc(t.task_code)}</strong><br><span class="muted">${esc(t.title)}</span></td>
      <td>${esc(t.assignee || '—')}</td><td>${badge(t.status)}</td>
      <td>${t.status === 'for_verification' ? `<button class="btn primary" data-vf="approve" data-id="${t.id}">Approve</button>
      <button class="btn" data-vf="reject" data-id="${t.id}">Reject</button>` : ''}</td></tr>`).join('')}</tbody></table></div>` : empty('Nothing awaiting verification.')}</div>`;
  c.querySelectorAll('[data-vf]').forEach(b => b.onclick = async () => {
    let remarks = '';
    if (b.dataset.vf === 'reject') { remarks = (prompt('Reason for rejection (required):') || '').trim(); if (!remarks) return; }
    try { await api(`/api/tasks/${b.dataset.id}/verify`, { method: 'POST', body: JSON.stringify({ decision: b.dataset.vf, remarks }) }); toast('Verification recorded.'); render(); }
    catch (e) { toast(e.message); }
  });
}
