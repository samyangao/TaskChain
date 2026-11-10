const NEXT = {
  submitted: ['under_review', 'cancelled'], under_review: ['cancelled'],
  assigned: ['accepted', 'handover', 'cancelled'],
  accepted: ['in_progress', 'waiting', 'handover', 'cancelled'],
  in_progress: ['waiting', 'handover', 'for_verification', 'cancelled'],
  waiting: ['in_progress', 'handover', 'cancelled'],
  handover: ['accepted', 'in_progress', 'cancelled'],
  rejected: ['in_progress', 'cancelled'], overdue: ['accepted', 'in_progress', 'waiting', 'handover', 'for_verification', 'cancelled'],
  for_verification: [], verified: [], completed: [], cancelled: []
};

function openModal(html, wide) {
  const m = document.createElement('div');
  m.className = 'modal-backdrop show';
  m.innerHTML = `<div class="modal" ${wide ? 'style="max-width:760px"' : ''}>${html}</div>`;
  document.body.appendChild(m);
  closeOnBackdrop(m);
  return m;
}

async function openTask(id) {
  try {
    const d = await api('/api/tasks/' + id);
    const t = d.task;
    const canAct = !['completed', 'cancelled'].includes(t.status);
    const canAssign = !['for_verification', 'verified', 'completed', 'cancelled'].includes(t.status);
    const pendingHO = (d.handovers || []).find(h => h.outcome === 'pending' && h.to_user_id === state.user.id && t.assigned_to === state.user.id);
    const canRespond = !pendingHO && t.assigned_to === state.user.id && !t.accepted_at && ['assigned', 'overdue', 'handover'].includes(t.status);
    const canHandOver = t.assigned_to && !pendingHO && (t.assigned_to === state.user.id || isManager()) && canAssign;
    // accepting and handing over have their own buttons / form, so they are not generic status steps
    const stepButtons = (NEXT[t.status] || []).filter(s => s !== 'accepted' && s !== 'handover');
    const blockedStep = s => d.blocked && !['submitted', 'under_review', 'assigned', 'cancelled', 'rejected'].includes(s);
    const m = openModal(`
      <div class="modal-head">
        <div><div class="eyebrow">${esc(t.task_code)}</div><h2>${esc(t.title)}</h2></div>
        <div class="modal-head-actions">
          <button class="btn small ${d.watching ? 'primary' : ''}" id="watchBtn" type="button">${d.watching ? 'Watching' : 'Watch'} · ${d.watchers.length}</button>
          <button class="modal-close">×</button>
        </div>
      </div>
      <div class="grid" style="gap:10px">
        <div class="notice">${badge(t.status)} <span class="priority-${esc(t.priority)}">${esc(t.priority)}</span>
          · ${esc(t.category)} · Due ${fmt(t.due_at)} ${slaChip(t.sla_state)}<br>
          <span class="muted">Requester: ${esc(t.requester)} · Responsible: ${esc(t.assignee || 'Unassigned')}</span>
          ${t.sla_due_at ? `<br><span class="muted small">SLA: due ${fmt(t.sla_due_at)} · escalates to coordinators ${fmt(t.sla_escalate_at)}${t.deadline ? ` · requester preferred ${fmt(t.deadline)}` : ''}</span>`
            : (t.deadline ? `<br><span class="muted small">No SLA for this category · requester preferred ${fmt(t.deadline)}</span>` : '')}
          ${t.location ? `<br><span class="muted">Location: ${esc(t.location)}</span>` : ''}</div>
        <div class="notice">${esc(t.description || 'No description.')}</div>
        ${d.blocked ? `<div class="notice blocked-notice"><strong>Blocked by dependencies.</strong> ${d.dependencies.filter(x => !x.met).map(x => `${esc(x.task_code)} (${esc(depStateLabel(x.required_state))})`).join(', ')}. This task cannot start, resume, be submitted for verification, or be completed until those tasks are done.</div>` : ''}
        ${(d.attachments || []).length ? `<div class="notice small"><strong>Attachments:</strong> ${attachmentLinks(d.attachments)}</div>` : ''}
        ${subtaskSectionHtml(d, t, canEditCollab(t))}
        ${dependencySectionHtml(d, t, canEditCollab(t))}
        ${completionHtml(d, t.created_by === state.user.id)}
        ${pendingHO ? `<div class="notice ho-pending"><strong>A handover is waiting for your acknowledgment</strong>
          ${handoverDetailHtml(pendingHO)}
          ${(() => { const p = pendingHO.items.filter(i => i.state === 'pending').length, b = pendingHO.items.filter(i => i.state === 'blocked').length;
            return (p || b) ? `<div class="small">Heads-up: ${p} item${p === 1 ? '' : 's'} still pending${b ? `, ${b} blocked` : ''}. You take custody of the task when you acknowledge.</div>` : ''; })()}
          <div class="form-actions"><button class="btn primary" id="ackBtn">Acknowledge handover</button><button class="btn" id="declineBtn">Decline</button></div></div>` : ''}
        ${canRespond ? `<div class="notice"><strong>This task is assigned to you.</strong>
          <div class="form-actions"><button class="btn primary" id="acceptBtn">Accept</button><button class="btn" id="declineBtn">Decline</button></div></div>` : ''}
        ${canAct && stepButtons.length ? `<div class="form-actions">
          ${stepButtons.map(s => `<button class="btn" data-status="${s}" ${blockedStep(s) ? 'disabled title="Blocked by dependencies"' : ''}>${statusLabel(s)}</button>`).join('')}</div>` : ''}
        ${isManager() && canAssign ? `<div class="notice" id="assignPanel"><strong>${t.assigned_to ? 'Reassign' : 'Assign'}</strong><div class="muted small">Loading suggestions…</div></div>` : ''}
        ${(canHandOver || (isManager() && canAct && !['verified'].includes(t.status))) ? `<div class="form-actions">
          ${canHandOver ? '<button class="btn" id="handoverBtn">Hand over task…</button>' : ''}
          ${isManager() && canAct && !['verified'].includes(t.status) ? '<button class="btn" id="escalateBtn">Escalate to administrators</button>' : ''}</div>` : ''}
        <h3>Time in custody</h3>
        ${custodyHtml(d.custody)}
        <h3>Handovers</h3>
        ${(d.handovers || []).length ? d.handovers.slice().reverse().map(handoverDetailHtml).join('') : empty('This task has not been handed over.')}
        <h3>Assignment history</h3>
        ${d.assignment_history.length ? `<div class="timeline">${d.assignment_history.map(h => `<div class="timeline-item"><div class="timeline-time">${fmt(h.created_at)}</div>
          <div class="timeline-body"><strong>${esc(historyText(h))}</strong>${h.reason ? `<p class="muted small">Reason: ${esc(h.reason)}</p>` : ''}</div></div>`).join('')}</div>` : empty('No assignment activity yet.')}
        ${commentsHtml(d)}
        ${watchersHtml(d)}
        <h3>Custody chain <span class="muted small">(${d.chain.length} records)</span></h3>
        <div id="chainStatus" aria-live="polite"></div>
        <div class="timeline">${d.chain.map(c => `<div class="timeline-item"><div class="timeline-time">${fmt(c.event_timestamp)}</div>
          <div class="timeline-body"><strong>#${c.sequence_number} ${esc(statusLabel(c.event_type))}</strong>
          <p class="muted small">${esc(c.actor_name || 'System')}</p></div></div>`).join('') || empty('No chain records.')}</div>
        ${state.user.role === 'administrator' ? `<div class="form-actions">
          <button class="btn" id="verifyChainBtn">Verify chain</button><button class="btn" id="reportBtn">Custody report</button></div>` : ''}
      </div>`, true);

    const reopen = () => { m.remove(); openTask(id); if (state.page !== 'dashboard') render(); };
    m.querySelectorAll('[data-status]').forEach(b => b.onclick = async () => {
      try { await api('/api/tasks/' + id, { method: 'PATCH', body: JSON.stringify({ status: b.dataset.status }) }); toast('Status updated.'); reopen(); }
      catch (e) { toast(e.message); }
    });
    const mentionInsert = m.querySelector('#mentionInsert');
    if (mentionInsert) mentionInsert.onclick = () => {
      const select = m.querySelector('#mentionSelect');
      const option = select.selectedOptions[0];
      if (!option || !option.value) return toast('Choose someone to mention.');
      const textarea = m.querySelector('#cmtText');
      const token = '@' + option.dataset.name + ' ';
      const start = textarea.selectionStart ?? textarea.value.length;
      const end = textarea.selectionEnd ?? start;
      textarea.value = textarea.value.slice(0, start) + token + textarea.value.slice(end);
      textarea.focus();
      textarea.selectionStart = textarea.selectionEnd = start + token.length;
      select.value = '';
    };
    m.querySelector('#cmtBtn').onclick = async () => {
      const text = m.querySelector('#cmtText').value.trim(); if (!text) return;
      const mentions = d.mentionable.filter(u => text.includes('@' + u.full_name)).map(u => u.id);
      try { await api(`/api/tasks/${id}/comments`, { method: 'POST', body: JSON.stringify({ text, mentions }) }); reopen(); }
      catch (e) { toast(e.message); }
    };
    const watchBtn = m.querySelector('#watchBtn');
    if (watchBtn) watchBtn.onclick = async () => {
      try { const r = await api(`/api/tasks/${id}/watch`, { method: 'POST' }); toast(r.message); reopen(); }
      catch (e) { toast(e.message); }
    };
    m.querySelectorAll('[data-subtask-toggle]').forEach(box => box.onchange = async () => {
      try { await api(`/api/tasks/${id}/subtasks/${box.dataset.subtaskToggle}`, { method: 'PATCH', body: JSON.stringify({ isDone: box.checked }) }); reopen(); }
      catch (e) { toast(e.message); reopen(); }
    });
    m.querySelectorAll('[data-subtask-delete]').forEach(btn => btn.onclick = async () => {
      if (!confirm('Remove this checklist item?')) return;
      try { await api(`/api/tasks/${id}/subtasks/${btn.dataset.subtaskDelete}`, { method: 'DELETE' }); toast('Checklist item removed.'); reopen(); }
      catch (e) { toast(e.message); }
    });
    const addSubtask = m.querySelector('#addSubtask');
    if (addSubtask) addSubtask.onclick = async () => {
      const input = m.querySelector('#subtaskTitle');
      const title = input.value.trim();
      if (!title) return toast('Enter a checklist item.');
      try { await api(`/api/tasks/${id}/subtasks`, { method: 'POST', body: JSON.stringify({ title }) }); reopen(); }
      catch (e) { toast(e.message); }
    };
    m.querySelectorAll('[data-dep-delete]').forEach(btn => btn.onclick = async () => {
      if (!confirm('Remove this dependency?')) return;
      try { await api(`/api/tasks/${id}/dependencies/${btn.dataset.depDelete}`, { method: 'DELETE' }); toast('Dependency removed.'); reopen(); }
      catch (e) { toast(e.message); }
    });
    const addDep = m.querySelector('#addDep');
    if (addDep) addDep.onclick = async () => {
      const dependsOnId = m.querySelector('#depSelect').value;
      if (!dependsOnId) return toast('Choose the task that must finish first.');
      try {
        await api(`/api/tasks/${id}/dependencies`, { method: 'POST', body: JSON.stringify({ dependsOnId, requiredState: m.querySelector('#depState').value }) });
        toast('Dependency added.'); reopen();
      } catch (e) { toast(e.message); }
    };
    if (m.querySelector('#depSelect')) loadDependencyOptions(m, id, d);
    const accept = m.querySelector('#acceptBtn');
    if (accept) accept.onclick = async () => {
      try { await api(`/api/tasks/${id}/accept`, { method: 'POST' }); toast('Task accepted.'); reopen(); }
      catch (e) { toast(e.message); }
    };
    const decline = m.querySelector('#declineBtn');
    if (decline) decline.onclick = async () => {
      const reason = await askReason({ title: 'Decline task', label: 'Why are you declining this task?', confirm: 'Decline task' });
      if (!reason) return;
      try {
        const r = await api(`/api/tasks/${id}/decline`, { method: 'POST', body: JSON.stringify({ reason }) });
        toast(r.message); m.remove(); render();  // the declined task is no longer yours, so do not reopen it
      } catch (e) { toast(e.message); }
    };
    const confirmBtn = m.querySelector('#confirmBtn');
    if (confirmBtn) confirmBtn.onclick = async () => {
      try { const r = await api(`/api/tasks/${id}/confirm`, { method: 'POST' }); toast(r.message); reopen(); }
      catch (e) { toast(e.message); }
    };
    const reopenBtn = m.querySelector('#reopenBtn');
    if (reopenBtn) reopenBtn.onclick = async () => {
      const reason = await askReason({ title: 'Reopen request', label: 'What is still not right?', confirm: 'Reopen request' });
      if (!reason) return;
      try { const r = await api(`/api/tasks/${id}/reopen`, { method: 'POST', body: JSON.stringify({ reason }) }); toast(r.message); reopen(); }
      catch (e) { toast(e.message); }
    };
    let chosenStar = 0;
    m.querySelectorAll('.star-btn').forEach(b => b.onclick = () => {
      chosenStar = parseInt(b.dataset.star, 10);
      m.querySelectorAll('.star-btn').forEach(x => x.setAttribute('aria-pressed', String(parseInt(x.dataset.star, 10) <= chosenStar)));
      m.querySelector('#ratingSubmit').disabled = false;
    });
    const rateBtn = m.querySelector('#ratingSubmit');
    if (rateBtn) rateBtn.onclick = async () => {
      if (!chosenStar) return toast('Choose a rating from 1 to 5.');
      try { const r = await api(`/api/tasks/${id}/rating`, { method: 'POST', body: JSON.stringify({ rating: chosenStar, comment: m.querySelector('#ratingComment').value }) }); toast(r.message); reopen(); }
      catch (e) { toast(e.message); }
    };
    const ack = m.querySelector('#ackBtn');
    if (ack) ack.onclick = async () => {
      try { const r = await api(`/api/tasks/${id}/handover/acknowledge`, { method: 'POST' }); toast(r.message); reopen(); }
      catch (e) { toast(e.message); }
    };
    const hoBtn = m.querySelector('#handoverBtn');
    if (hoBtn) hoBtn.onclick = () => handoverModal(id, () => { m.remove(); render(); });
    const escalate = m.querySelector('#escalateBtn');
    if (escalate) escalate.onclick = async () => {
      const reason = await askReason({ title: 'Escalate to administrators', label: 'Why does this need escalating?', confirm: 'Escalate' });
      if (!reason) return;
      try { const r = await api(`/api/tasks/${id}/escalate`, { method: 'POST', body: JSON.stringify({ reason }) }); toast(r.message); reopen(); }
      catch (e) { toast(e.message); }
    };
    if (isManager() && canAssign) loadAssignPanel(m, t, id, reopen);
    const vc = m.querySelector('#verifyChainBtn');
    if (vc) vc.onclick = async () => {
      const slot = m.querySelector('#chainStatus');
      vc.disabled = true; vc.textContent = 'Verifying…';
      try {
        const r = await api(`/api/tasks/${id}/chain/verify`, { method: 'POST' });
        slot.innerHTML = chainStatusCard(r);
      } catch (e) { slot.innerHTML = `<div class="notice">Verification failed to run: ${esc(e.message)}</div>`; }
      vc.disabled = false; vc.textContent = 'Verify chain';
    };
    const rb = m.querySelector('#reportBtn');
    if (rb) rb.onclick = () => chainReportModal(id).catch(e => toast(e.message));
  } catch (e) { toast(e.message); }
}
