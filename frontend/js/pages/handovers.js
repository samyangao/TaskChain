async function handoverPage(c) {
  setHeader('Handover');
  const [d, pend] = await Promise.all([api('/api/tasks'), api('/api/handovers/pending')]);
  const blocked = ['for_verification', 'verified', 'completed', 'cancelled'];
  const waitingIds = new Set(pend.handovers.map(h => h.task_id));
  const mine = d.tasks.filter(t => t.assigned_to && !blocked.includes(t.status) && !waitingIds.has(t.id) &&
    (isManager() || t.assigned_to === state.user.id));
  c.innerHTML = `
    ${pend.handovers.length ? `<div class="card" style="margin-bottom:16px"><div class="card-title"><h3>Waiting for your acknowledgment</h3></div>
      <div class="table-wrap"><table class="table"><thead><tr><th>Task</th><th>From</th><th>Sent</th><th></th></tr></thead><tbody>${
        pend.handovers.map(h => `<tr><td><strong>${esc(h.task_code)}</strong><br><span class="muted">${esc(h.title)}</span></td><td>${esc(h.from_name)}</td><td>${fmt(h.created_at)}</td>
          <td><button class="btn primary" data-review="${h.task_id}">Review &amp; acknowledge</button></td></tr>`).join('')}</tbody></table></div></div>` : ''}
    <div class="card"><div class="card-title"><h3>Tasks you can hand over</h3></div>${
    mine.length ? `<div class="notice small">Only assigned tasks can be handed over. The new holder must acknowledge the handover before it takes effect.</div><div class="table-wrap"><table class="table"><thead><tr><th>Task</th><th>Responsible</th><th>Status</th><th></th></tr></thead><tbody>${
      mine.map(t => `<tr><td><strong>${esc(t.task_code)}</strong><br><span class="muted">${esc(t.title)}</span></td>
      <td>${esc(t.assignee || 'Unassigned')}</td><td>${badge(t.status)}</td>
      <td><button class="btn" data-ho="${t.id}">Hand over</button></td></tr>`).join('')}</tbody></table></div>` : empty('Nothing to hand over. Assign a task to someone first, then it appears here.')}</div>`;
  c.querySelectorAll('[data-ho]').forEach(b => b.onclick = () => handoverModal(b.dataset.ho));
  c.querySelectorAll('[data-review]').forEach(b => b.onclick = () => openTask(b.dataset.review));
}

const DEFAULT_CHECKLIST = [
  ['Task information received', 'done'], ['Required files received', 'done'], ['Testing completed', 'pending'],
  ['Documentation completed', 'pending'], ['Blocker resolved', 'pending']
];

async function handoverModal(id, onDone) {
  let d;
  try { d = await api(`/api/tasks/${id}/handover-recipients`); } catch (e) { return toast(e.message); }
  if (!d.recipients.length) return toast('There is nobody to hand this task to.');
  const rowHtml = (label, state) => `<div class="cl-row"><input class="input cl-label" maxlength="160" value="${esc(label)}" placeholder="Checklist item">
    <select class="select cl-state"><option value="done"${state === 'done' ? ' selected' : ''}>DONE</option><option value="pending"${state === 'pending' ? ' selected' : ''}>PENDING</option><option value="blocked"${state === 'blocked' ? ' selected' : ''}>BLOCKED</option></select>
    <button type="button" class="btn small cl-remove" aria-label="Remove item">×</button></div>`;
  const fit = { match: 'team match', no_team_required: 'any team', different_team: 'different team' };
  const m = openModal(`
    <div class="modal-head"><div><div class="eyebrow">Handover</div><h2>Hand over task</h2></div><button class="modal-close" aria-label="Close">×</button></div>
    <div class="form-grid">
      <div class="form-field full-span"><label>Recipient</label><select class="select" id="hoTo">${d.recipients.map(u =>
        `<option value="${esc(u.id)}">${esc(u.full_name)} (${esc(u.role)}) · ${u.active_tasks} active · ${fit[u.compatibility]}${u.note ? ' · ' + esc(u.note) : ''}</option>`).join('')}</select>
        <span class="small muted">${d.team ? `Category team: ${esc(d.team)}.` : ''} The handover takes effect when the recipient acknowledges it.</span></div>
      <div class="form-field full-span"><label>Reason</label><input class="input" id="hoReason" maxlength="255"></div>
      <div class="form-field full-span"><label>Checklist</label><div id="hoChecklist">${DEFAULT_CHECKLIST.map(([l, st]) => rowHtml(l, st)).join('')}</div>
        <button type="button" class="btn small" id="hoAddItem">Add item</button></div>
      <div class="form-field full-span"><label>Blockers</label><textarea class="textarea" id="hoBlockers" maxlength="1000" placeholder="Required if any item is BLOCKED"></textarea></div>
      <div class="form-field full-span"><label>Files (optional)</label><input type="file" id="hoFiles" multiple accept=".jpg,.jpeg,.png,.gif,.webp,.pdf,.txt,.doc,.docx,.xls,.xlsx,.csv">
        <span class="small muted">Up to 5 files, 5 MB each (images, PDF, text, Word, Excel, CSV).</span></div>
      <div class="form-field full-span"><label>Notes</label><textarea class="textarea" id="hoNotes" maxlength="2000"></textarea></div>
      <div class="form-actions full-span"><button class="btn primary" id="hoGo">Send handover</button></div>
    </div>`);
  const list = m.querySelector('#hoChecklist');
  const wire = () => list.querySelectorAll('.cl-remove').forEach(b => b.onclick = () => { if (list.children.length > 1) b.closest('.cl-row').remove(); else toast('Keep at least one checklist item.'); });
  wire();
  m.querySelector('#hoAddItem').onclick = () => {
    if (list.children.length >= 20) return toast('A checklist can have at most 20 items.');
    list.insertAdjacentHTML('beforeend', rowHtml('', 'pending')); wire(); list.lastElementChild.querySelector('.cl-label').focus();
  };
  m.querySelector('#hoGo').onclick = async () => {
    const checklist = [...list.querySelectorAll('.cl-row')].map(r => ({ label: r.querySelector('.cl-label').value.trim(), state: r.querySelector('.cl-state').value }));
    if (checklist.some(i => !i.label)) return toast('Give every checklist item a label (or remove it).');
    const blockers = m.querySelector('#hoBlockers').value.trim();
    if (checklist.some(i => i.state === 'blocked') && !blockers) return toast('An item is BLOCKED: describe what is blocking it.');
    if (!m.querySelector('#hoReason').value.trim()) return toast('Give a reason for the handover.');
    const fd = new FormData();
    fd.append('payload', JSON.stringify({ toUser: m.querySelector('#hoTo').value, reason: m.querySelector('#hoReason').value,
      notes: m.querySelector('#hoNotes').value, blockers, checklist }));
    [...m.querySelector('#hoFiles').files].forEach(f => fd.append('files', f));
    const go = m.querySelector('#hoGo'); go.disabled = true;
    try {
      const r = await api(`/api/tasks/${id}/handover`, { method: 'POST', body: fd });
      m.remove(); toast(r.message); (onDone || render)();
    } catch (e) { go.disabled = false; toast(e.message); }
  };
}
