async function verificationPage(c) {
  setHeader('Verification');
  if (!['administrator', 'coordinator', 'verifier'].includes(state.user.role)) {
    c.innerHTML = `<div class="card">${empty('Only verifiers can review completed work.')}</div>`;
    return;
  }

  const d = await api('/api/verifications');
  const awaiting = d.tasks.filter(t => t.status === 'for_verification');
  const verified = d.tasks.filter(t => t.status === 'verified');
  const oldest = awaiting.length
    ? awaiting.reduce((a, b) => new Date(a.updated_at) < new Date(b.updated_at) ? a : b)
    : null;
  const oldestHours = oldest ? Math.max(1, Math.floor((Date.now() - new Date(oldest.updated_at).getTime()) / 3600000)) : null;
  const oldestLabel = oldestHours == null ? '—' : oldestHours >= 24 ? `${Math.floor(oldestHours / 24)}d` : `${oldestHours}h`;

  c.innerHTML = `
    <div class="grid stats">
      <div class="stat attention"><div class="stat-icon" aria-hidden="true">${ICONS.verification}</div><div class="label">Awaiting review</div><div class="num">${awaiting.length}</div><div class="sub">Ready for sign-off</div></div>
      <div class="stat overdue"><div class="stat-icon" aria-hidden="true">${ICONS.sla}</div><div class="label">Oldest waiting</div><div class="num">${esc(oldestLabel)}</div><div class="sub">Longest in queue</div></div>
      <div class="stat completed"><div class="stat-icon" aria-hidden="true">${ICONS.done}</div><div class="label">Verified records</div><div class="num">${verified.length}</div><div class="sub">Marked verified</div></div>
      <div class="stat"><div class="stat-icon" aria-hidden="true">${ICONS.total}</div><div class="label">Queue total</div><div class="num">${d.tasks.length}</div><div class="sub">Current and recent</div></div>
    </div>

    <div class="card">
      <div class="card-title"><h3>Awaiting verification</h3><span class="small muted">${awaiting.length} waiting</span></div>
      ${awaiting.length ? `<div class="action-list">${awaiting.map(t => `
        <div class="action-item">
          <div class="action-icon amber" aria-hidden="true">${ICONS.verification}</div>
          <div class="action-copy">
            <strong>${esc(t.task_code)} · ${esc(t.title)}</strong>
            <small>${esc(t.assignee || 'Unassigned')} · completed ${fmt(t.completed_at || t.updated_at)} · ${esc(t.requester || 'Unknown requester')}</small>
          </div>
          <div class="action-actions">
            <button class="btn small" data-review="${esc(t.id)}">Review evidence</button>
            <button class="btn primary small" data-verdict="approve" data-id="${esc(t.id)}">Approve</button>
            <button class="btn danger small" data-verdict="reject" data-id="${esc(t.id)}">Reject…</button>
          </div>
        </div>`).join('')}</div>` : empty('Nothing awaiting verification.')}
    </div>

    <div class="small muted" style="margin-top:10px">Approved requests move to Completed and leave this queue.</div>

    ${verified.length ? `<div class="card">
      <div class="card-title"><h3>Recently verified</h3><span class="small muted">${verified.length}</span></div>
      ${taskTable(verified.slice(0, 5))}
    </div>` : ''}`;

  c.querySelectorAll('[data-review]').forEach(btn => {
    btn.onclick = () => openTask(btn.dataset.review, 'evidence');
  });
  c.querySelectorAll('[data-verdict]').forEach(btn => {
    btn.onclick = () => {
      const task = awaiting.find(t => t.id === btn.dataset.id);
      if (task) verificationDecisionModal(task, btn.dataset.verdict, () => render());
    };
  });
  c.querySelectorAll('[data-task]').forEach(el => {
    el.onclick = () => openTask(el.dataset.task);
  });
}

function verificationDecisionModal(task, decision, onDone) {
  const reject = decision === 'reject';
  const m = openModal(`
    <div class="modal-head">
      <div><div class="eyebrow">${esc(task.task_code)}</div><h2>${reject ? 'Reject completion' : 'Approve completion'}</h2></div>
      <button class="modal-close" aria-label="Close">×</button>
    </div>
    <div class="notice task-summary">
      ${badge(task.status)} <strong>${esc(task.title)}</strong><br>
      <span class="muted">${esc(task.requester || 'Unknown requester')} · handled by ${esc(task.assignee || 'Unassigned')} · completed ${fmt(task.completed_at || task.updated_at)}</span>
    </div>
    <div class="form-grid">
      <div class="form-field full-span">
        <label for="verifyRemarks">${reject ? 'Reason for rejection' : 'Remarks'} ${reject ? '<span class="req" aria-hidden="true">*</span>' : '<span class="muted">(optional)</span>'}</label>
        <textarea class="textarea" id="verifyRemarks" maxlength="1000"
          placeholder="${reject ? 'Explain what needs to be corrected before this can be approved.' : 'Add any notes for the record.'}"
          aria-describedby="verifyRemarksHint verifyRemarksError"></textarea>
        <span class="form-help" id="verifyRemarksHint">${reject ? 'The requester and personnel will be notified with this reason.' : 'This note is stored with the verification record.'}</span>
        <span class="field-error" id="verifyRemarksError" role="alert"></span>
      </div>
      <div class="form-actions full-span">
        <button type="button" class="btn" id="verifyCancel">Cancel</button>
        <button type="button" class="btn ${reject ? 'danger' : 'primary'}" id="verifyConfirm">${reject ? 'Reject completion' : 'Approve completion'}</button>
      </div>
    </div>`);

  const close = () => m.remove();
  m.querySelector('#verifyCancel').onclick = close;
  m.querySelector('#verifyConfirm').onclick = async () => {
    const remarks = m.querySelector('#verifyRemarks').value.trim();
    const error = m.querySelector('#verifyRemarksError');
    const field = m.querySelector('#verifyRemarks');
    if (reject && !remarks) {
      field.setAttribute('aria-invalid', 'true');
      error.textContent = 'Give a reason before rejecting this completion.';
      field.focus();
      return;
    }
    field.removeAttribute('aria-invalid');
    error.textContent = '';
    const button = m.querySelector('#verifyConfirm');
    button.disabled = true;
    button.textContent = 'Recording…';
    try {
      await api(`/api/tasks/${task.id}/verify`, {
        method: 'POST',
        body: JSON.stringify({ decision, remarks })
      });
      toast(reject ? 'Completion rejected.' : 'Completion approved.');
      m.remove();
      if (onDone) onDone();
      else render();
    } catch (e) {
      error.textContent = e.message || 'Could not record the verification decision.';
      toast(e.message || 'Could not record the verification decision.');
      button.disabled = false;
      button.textContent = reject ? 'Reject completion' : 'Approve completion';
    }
  };
}
