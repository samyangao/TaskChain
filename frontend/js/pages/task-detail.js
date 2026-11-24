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

// Display-only workflow stages. They group the real backend statuses and never
// add or rename a status. "waiting", "overdue" and "rejected" are shown as the
// current state of the work stage.
const WORKFLOW_STAGES = [
  { key: 'submitted', label: 'Submitted' },
  { key: 'under_review', label: 'Review' },
  { key: 'assigned', label: 'Assigned' },
  { key: 'accepted', label: 'Accepted' },
  { key: 'in_progress', label: 'In Progress' },
  { key: 'handover', label: 'Handover' },
  { key: 'for_verification', label: 'Verification' },
  { key: 'completed', label: 'Completed' }
];

function workflowStageIndex(status) {
  if (status === 'cancelled') return -1;
  if (status === 'submitted') return 0;
  if (status === 'under_review') return 1;
  if (status === 'assigned') return 2;
  if (status === 'accepted') return 3;
  if (['in_progress', 'waiting', 'overdue', 'rejected'].includes(status)) return 4;
  if (status === 'handover') return 5;
  if (status === 'for_verification') return 6;
  if (['completed', 'verified'].includes(status)) return 7;
  return 0;
}

function workflowStageTime(t, chain, key) {
  if (key === 'submitted') return t.created_at;
  if (key === 'accepted' && t.accepted_at) return t.accepted_at;
  if (key === 'completed' && (t.completed_at || t.confirmed_at)) return t.completed_at || t.confirmed_at;

  const statusEvent = (chain || []).find(c =>
    c.event_type === 'status_changed' && c.event_data && c.event_data.to_status === key
  );
  if (statusEvent) return statusEvent.event_timestamp;

  if (key === 'overdue') {
    const overdue = (chain || []).find(c => c.event_type === 'task_overdue');
    if (overdue) return overdue.event_timestamp;
  }
  if (key === 'accepted') {
    const accepted = (chain || []).find(c => c.event_type === 'task_accepted');
    if (accepted) return accepted.event_timestamp;
  }
  if (key === 'handover') {
    const handover = (chain || []).find(c => c.event_type === 'handover_created');
    if (handover) return handover.event_timestamp;
  }
  if (key === 'completed') {
    const completed = (chain || []).find(c => ['task_verified', 'task_completed', 'task_confirmed'].includes(c.event_type));
    if (completed) return completed.event_timestamp;
  }
  return null;
}

function workflowTimelineHtml(t, chain, hasHandover = false) {
  if (t.status === 'cancelled') {
    return `<div class="notice cancelled-notice"><strong>Request cancelled.</strong> This request is no longer moving through the workflow.</div>`;
  }

  const current = workflowStageIndex(t.status);
  const tone = { waiting: 'amber', overdue: 'red', rejected: 'red' }[t.status] || '';
  return `<div class="task-workflow" role="group" aria-label="Request progress">
    <ol class="workflow-steps">
      ${WORKFLOW_STAGES.map((stage, index) => {
        let state = index < current ? 'done' : index === current ? 'current' : 'pending';
        if (stage.key === 'handover' && index < current && !hasHandover) state = 'skipped';
        const label = state === 'current' ? statusLabel(t.status) : stage.label;
        const timeKey = state === 'current' && ['waiting', 'overdue', 'rejected'].includes(t.status) ? t.status : stage.key;
        const time = state === 'done' || state === 'current' ? workflowStageTime(t, chain, timeKey) : null;
        return `<li class="workflow-step ${state}${state === 'current' && tone ? ' ' + tone : ''}"${state === 'current' ? ' aria-current="step"' : ''}>
          <span class="workflow-node" aria-hidden="true">${state === 'done' ? '✓' : state === 'skipped' ? '–' : index + 1}</span>
          <span class="workflow-copy"><strong>${esc(label)}</strong>${time ? `<small>${fmt(time)}</small>` : state === 'skipped' ? '<small>Not used</small>' : state === 'current' ? '<small>Current</small>' : ''}</span>
        </li>`;
      }).join('')}
    </ol>
  </div>`;
}

function nextActionText(t, pendingHandover) {
  const isRequester = t.created_by === state.user.id;
  if (pendingHandover) return 'A handover is waiting for your acknowledgment. Review the checklist, then acknowledge or decline it.';
  if (t.status === 'completed' && !t.confirmed_at) {
    return isRequester
      ? 'The work is finished. Confirm completion, or reopen the request if something is not right.'
      : 'Waiting for the requester to confirm or reopen the completed work.';
  }
  if (t.status === 'completed') {
    return isRequester ? 'Nothing is required. You can rate this request if you have not already.' : 'This request is complete.';
  }
  if (t.status === 'cancelled') return 'This request was cancelled. No further action is required.';
  if (t.status === 'for_verification') {
    return ['verifier', 'coordinator', 'administrator'].includes(state.user.role)
      ? 'Review the evidence and completion notes, then approve or reject the work.'
      : 'The completed work is waiting for verification. No action is required from you.';
  }
  if (t.status === 'assigned' && t.assigned_to === state.user.id && !t.accepted_at) {
    return 'Accept or decline this assignment so the coordinator knows you can take it.';
  }
  if (isManager() && !t.assigned_to && ['submitted', 'under_review', 'overdue'].includes(t.status)) {
    return 'Assign this request to personnel so work can start.';
  }
  if (isManager() && t.status === 'overdue') return 'Follow up on this overdue request or reassign it.';
  if (t.status === 'overdue') return 'This request is past its expected date. The team has been notified.';
  if (t.status === 'rejected') return 'Review the rejection reason, then resume work when the issue is resolved.';
  if (t.status === 'waiting') return 'Work is paused until the blocker is cleared. Resume it when ready.';
  if (t.status === 'handover') return 'The handover is waiting for the recipient to acknowledge it.';
  if (t.status === 'in_progress' || t.status === 'accepted') {
    return isRequester
      ? 'The team is working on your request. You will be notified when your confirmation is needed.'
      : 'Continue the work, then send a handover or submit it for verification.';
  }
  return isRequester
    ? 'The team has your request. You will be notified when your confirmation is needed.'
    : 'Monitor this request for the next update.';
}

function openModal(html, wide) {
  const m = document.createElement('div');
  m.className = 'modal-backdrop show';
  m.innerHTML = `<div class="modal" ${wide ? 'style="max-width:760px"' : ''}>${html}</div>`;
  document.body.appendChild(m);
  closeOnBackdrop(m);
  return m;
}

async function openTask(id, initialTab = 'overview') {
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
    const chain = d.chain || [];
    const tabButtons = [
      ['overview', 'Overview'],
      ['details', 'Details'],
      ['handover', `Handover${(d.handovers || []).length ? ` (${(d.handovers || []).length})` : ''}`],
      ['evidence', `Evidence${(d.attachments || []).length ? ` (${(d.attachments || []).length})` : ''}`],
      ['comments', `Comments${(d.comments || []).length ? ` (${(d.comments || []).length})` : ''}`],
      ['chain', 'Task Chain'],
      ['history', 'History']
    ];
    let activeTab = tabButtons.some(([key]) => key === initialTab) ? initialTab : 'overview';
    const panel = (key, content) => `<section class="task-tab-panel" id="taskPanel-${key}" role="tabpanel" aria-labelledby="taskTab-${key}"${key === activeTab ? '' : ' hidden'}>${content}</section>`;

    const overviewHtml = `
      <div class="notice task-summary">${badge(t.status)} <span class="priority-${esc(t.priority)}">${esc(t.priority)}</span>
        · ${esc(t.category)} · Due ${fmt(t.due_at)} ${slaChip(t.sla_state)}<br>
        <span class="muted">Requester: ${esc(t.requester)} · Responsible: ${esc(t.assignee || 'Unassigned')}</span>
        ${t.sla_due_at ? `<br><span class="muted small">SLA: due ${fmt(t.sla_due_at)} · escalates to coordinators ${fmt(t.sla_escalate_at)}${t.deadline ? ` · requester preferred ${fmt(t.deadline)}` : ''}</span>`
          : (t.deadline ? `<br><span class="muted small">No SLA for this category · requester preferred ${fmt(t.deadline)}</span>` : '')}
        ${t.location ? `<br><span class="muted">Location: ${esc(t.location)}</span>` : ''}</div>
      <div class="notice task-description">${esc(t.description || 'No description.')}</div>
      ${d.blocked ? `<div class="notice blocked-notice"><strong>Blocked by dependencies.</strong> ${d.dependencies.filter(x => !x.met).map(x => `${esc(x.task_code)} (${esc(depStateLabel(x.required_state))})`).join(', ')}. This task cannot start, resume, be submitted for verification, or be completed until those tasks are done.</div>` : ''}
      ${workflowTimelineHtml(t, chain, (d.handovers || []).length > 0)}
      <div class="notice next-action"><strong>What happens next:</strong> ${esc(nextActionText(t, pendingHO))}</div>
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
        ${isManager() && canAct && !['verified'].includes(t.status) ? '<button class="btn" id="escalateBtn">Escalate to administrators</button>' : ''}</div>` : ''}`;

    const detailsHtml = `
      ${subtaskSectionHtml(d, t, canEditCollab(t))}
      ${dependencySectionHtml(d, t, canEditCollab(t))}`;

    const handoverHtml = `
      <h3>Time in custody</h3>
      ${custodyHtml(d.custody)}
      <h3>Handovers</h3>
      ${(d.handovers || []).length ? d.handovers.slice().reverse().map(handoverDetailHtml).join('') : empty('This task has not been handed over.')}`;

    const evidenceHtml = `
      <h3>Request attachments <span class="muted small">${(d.attachments || []).length}</span></h3>
      ${(d.attachments || []).length ? `<div class="notice small">${attachmentLinks(d.attachments)}</div>` : empty('No files were attached to the request.')}
      <div class="small muted" style="margin-top:10px">Files attached to handovers are listed in the Handover tab.</div>`;

    const commentsPanelHtml = `
      ${commentsHtml(d)}
      ${watchersHtml(d)}`;

    const chainHtml = `
      <h3>Custody chain <span class="muted small">(${chain.length} records)</span></h3>
      <div id="chainStatus" aria-live="polite"></div>
      <div class="timeline">${chain.map(c => `<div class="timeline-item"><div class="timeline-time">${fmt(c.event_timestamp)}</div>
        <div class="timeline-body"><strong>#${c.sequence_number} ${esc(statusLabel(c.event_type))}</strong>
        <p class="muted small">${esc(c.actor_name || 'System')}</p></div></div>`).join('') || empty('No chain records.')}</div>
      ${state.user.role === 'administrator' ? `<div class="form-actions">
        <button class="btn" id="verifyChainBtn">Verify chain</button><button class="btn" id="reportBtn">Custody report</button></div>` : ''}`;

    const historyHtml = `
      <h3>Assignment history</h3>
      ${(d.assignment_history || []).length ? `<div class="timeline">${d.assignment_history.map(h => `<div class="timeline-item"><div class="timeline-time">${fmt(h.created_at)}</div>
        <div class="timeline-body"><strong>${esc(historyText(h))}</strong>${h.reason ? `<p class="muted small">Reason: ${esc(h.reason)}</p>` : ''}</div></div>`).join('')}</div>` : empty('No assignment activity yet.')}`;

    const m = openModal(`
      <div class="modal-head">
        <div><div class="eyebrow">${esc(t.task_code)}</div><h2>${esc(t.title)}</h2></div>
        <div class="modal-head-actions">
          <button class="btn small ${d.watching ? 'primary' : ''}" id="watchBtn" type="button">${d.watching ? 'Watching' : 'Watch'} · ${d.watchers.length}</button>
          <button class="modal-close">×</button>
        </div>
      </div>
      <div class="task-tabs" role="tablist" aria-label="Task sections">
        ${tabButtons.map(([key, label]) => `<button type="button" class="task-tab${key === activeTab ? ' active' : ''}" id="taskTab-${key}" role="tab" aria-selected="${key === activeTab}" aria-controls="taskPanel-${key}" data-tab="${key}">${label}</button>`).join('')}
      </div>
      <div class="task-tab-panels">
        ${panel('overview', overviewHtml)}
        ${panel('details', detailsHtml)}
        ${panel('handover', handoverHtml)}
        ${panel('evidence', evidenceHtml)}
        ${panel('comments', commentsPanelHtml)}
        ${panel('chain', chainHtml)}
        ${panel('history', historyHtml)}
      </div>`, true);

    m.querySelectorAll('[data-tab]').forEach(tab => {
      tab.onclick = () => {
        activeTab = tab.dataset.tab;
        m.querySelectorAll('[data-tab]').forEach(item => {
          const active = item === tab;
          item.classList.toggle('active', active);
          item.setAttribute('aria-selected', String(active));
        });
        m.querySelectorAll('.task-tab-panel').forEach(panel => {
          panel.hidden = panel.id !== `taskPanel-${tab.dataset.tab}`;
        });
      };
      tab.onkeydown = e => {
        if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(e.key)) return;
        e.preventDefault();
        const tabs = [...m.querySelectorAll('[data-tab]')];
        const index = tabs.indexOf(tab);
        const next = e.key === 'Home' ? tabs[0] : e.key === 'End' ? tabs[tabs.length - 1]
          : tabs[(index + (e.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length];
        next.focus();
        next.click();
      };
    });

    const reopen = () => { m.remove(); openTask(id, activeTab); if (state.page !== 'dashboard') render(); };
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
