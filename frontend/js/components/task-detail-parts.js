const fmtDuration = secs => {
  secs = Math.max(0, Math.round(secs));
  const d = Math.floor(secs / 86400), h = Math.floor((secs % 86400) / 3600), mi = Math.floor((secs % 3600) / 60);
  if (d) return `${d}d ${h}h`;
  if (h) return `${h}h ${mi}m`;
  if (mi) return `${mi}m`;
  return '< 1m';
};
const fmtSize = b => b >= 1048576 ? `${(b / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(b / 1024))} KB`;
const itemBadge = st => ({
  done: '<span class="badge badge-green">DONE</span>',
  pending: '<span class="badge badge-orange">PENDING</span>',
  blocked: '<span class="badge badge-red">BLOCKED</span>'
})[st] || esc(st);
const outcomeBadge = o => ({
  pending: '<span class="badge badge-orange">Awaiting acknowledgment</span>',
  acknowledged: '<span class="badge badge-green">Acknowledged</span>',
  declined: '<span class="badge badge-red">Declined</span>',
  superseded: '<span class="badge badge-gray">Replaced</span>'
})[o] || esc(o);

function handoverDetailHtml(h) {
  return `<div class="notice ho-block">
    <div><strong>${esc(h.from_name)} → ${esc(h.to_name)}</strong> ${outcomeBadge(h.outcome)}<br>
      <span class="muted small">${fmt(h.created_at)}${h.initiated_by_name && h.initiated_by_name !== h.from_name ? ` · started by ${esc(h.initiated_by_name)}` : ''}${h.resolved_at ? ` · resolved ${fmt(h.resolved_at)}` : ''}</span></div>
    <div class="small">Reason: ${esc(h.reason)}</div>
    ${h.items.length ? `<ul class="checklist">${h.items.map(i => `<li>${itemBadge(i.state)} ${esc(i.label)}</li>`).join('')}</ul>` : ''}
    ${h.blockers ? `<div class="small"><strong>Blockers:</strong> ${esc(h.blockers)}</div>` : ''}
    ${h.notes ? `<div class="small"><strong>Notes:</strong> ${esc(h.notes)}</div>` : ''}
    ${h.attachments.length ? `<div class="small"><strong>Files:</strong> ${h.attachments.map(a => `<a href="${esc(a.url)}" target="_blank" rel="noopener">${esc(a.filename)}</a> <span class="muted">(${fmtSize(a.size_bytes)})</span>`).join(' · ')}</div>` : ''}
  </div>`;
}

const START_WORDS = { accepted: 'accepting the task', acknowledged: 'acknowledging a handover' };
const END_WORDS = { handed_over: 'handed over', reassigned: 'reassigned', returned: 'returned to the coordinators', completed: 'completed', verified: 'verified', cancelled: 'cancelled', replaced: 'replaced' };
function custodyHtml(cu) {
  if (!cu || !cu.periods.length) return empty('No custody recorded yet. It starts when someone accepts the task or acknowledges a handover.');
  return `<div class="timeline">${cu.periods.map(p => `<div class="timeline-item"><div class="timeline-time">${fmt(p.started_at)}</div>
    <div class="timeline-body"><strong>${esc(p.holder_name)} · ${fmtDuration(p.seconds)}${p.open ? ' <span class="badge badge-green">Holding now</span>' : ''}</strong>
      <p class="muted small">Started by ${START_WORDS[p.start_reason] || esc(p.start_reason)}${p.open ? '' : ` · ended ${fmt(p.ended_at)} (${END_WORDS[p.end_reason] || esc(p.end_reason)})`}</p></div></div>`).join('')}</div>
    <div class="small muted">Total time in custody: ${cu.totals.map(t => `${esc(t.holder_name)} ${fmtDuration(t.seconds)}`).join(' · ')}</div>`;
}

const ATTACH_TYPES = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.pdf', '.txt', '.doc', '.docx', '.xls', '.xlsx', '.csv'];
const attachmentLinks = list => list.map(a => `<a href="${esc(a.url)}" target="_blank" rel="noopener">${esc(a.filename)}</a> <span class="muted">(${fmtSize(a.size_bytes)})</span>`).join(' · ');
const stars = n => '★'.repeat(n) + '☆'.repeat(5 - n);

function completionHtml(d, isRequester) {
  const comp = d.completion || {};
  const reopened = comp.reopen_count ? `<div class="small muted">This request was reopened ${comp.reopen_count} time${comp.reopen_count === 1 ? '' : 's'}.</div>` : '';
  if (comp.state === 'awaiting') {
    return `<div class="notice completed-banner"><div class="completed-title">REQUEST COMPLETED</div>
      <div>${isRequester ? 'The work on this request is finished. Please confirm that it is done, or reopen it if it is not.' : 'Waiting for the requester to confirm or reopen it.'}</div>
      ${comp.auto_close_at ? `<div class="small muted">If there is no response it closes automatically on ${fmt(comp.auto_close_at)}.</div>` : '<div class="small muted">It will not close automatically.</div>'}
      ${isRequester ? '<div class="form-actions"><button class="btn primary" id="confirmBtn">Confirm complete</button><button class="btn" id="reopenBtn">Reopen request</button></div>' : ''}${reopened}</div>`;
  }
  if (['confirmed', 'auto_closed', 'legacy'].includes(comp.state)) {
    const how = { confirmed: `confirmed by the requester on ${fmt(comp.confirmed_at)}`, auto_closed: `closed automatically on ${fmt(comp.confirmed_at)} (no response)`, legacy: 'completed before confirmations were introduced' }[comp.state];
    let rate = '';
    if (d.rating) {
      rate = `<div class="rating-done"><strong>Rating: ${stars(d.rating.rating)} ${d.rating.rating}/5</strong>${d.rating.comment ? `<p class="small">${esc(d.rating.comment)}</p>` : ''}</div>`;
    } else if (isRequester && comp.rateable) {
      rate = `<div class="rating-box"><strong>How was this request handled?</strong>
        <div class="rating-stars" role="group" aria-label="Rating from 1 to 5">${[1, 2, 3, 4, 5].map(n => `<button type="button" class="star-btn" data-star="${n}" aria-pressed="false" aria-label="${n} out of 5">${n} ★</button>`).join('')}</div>
        <textarea class="textarea" id="ratingComment" maxlength="1000" placeholder="Comment (optional)"></textarea>
        <div class="form-actions"><button class="btn primary" id="ratingSubmit" disabled>Submit rating</button></div></div>`;
    }
    return `<div class="notice"><strong>Closed</strong> · ${how}${reopened}${rate}</div>`;
  }
  return comp.reopen_count ? `<div class="small muted">This request was reopened ${comp.reopen_count} time${comp.reopen_count === 1 ? '' : 's'}.</div>` : '';
}

function historyText(h) {
  const who = h.actor_name;
  return ({
    assigned: `${who} assigned the task to ${h.to_name}`,
    reassigned: `${who} reassigned the task from ${h.from_name || '—'} to ${h.to_name}`,
    accepted: `${who} accepted the task`,
    declined: `${who} declined the task`,
    escalated: `${who} escalated the task to the administrators`,
    handed_over: `${who} handed the task over from ${h.from_name || '—'} to ${h.to_name}`,
    reopened: `${who} reopened the request`
  })[h.event] || `${who}: ${h.event}`;
}

function askReason({ title, label, confirm }) {
  return new Promise(resolve => {
    const m = openModal(`
      <div class="modal-head"><div><div class="eyebrow">Reason required</div><h2>${esc(title)}</h2></div><button class="modal-close" aria-label="Close">×</button></div>
      <div class="form-grid">
        <div class="form-field full-span"><label>${esc(label)}</label><textarea class="textarea" id="reasonText" maxlength="500"></textarea></div>
        <div class="form-actions full-span"><button class="btn" id="reasonCancel">Cancel</button><button class="btn primary" id="reasonOk">${esc(confirm)}</button></div>
      </div>`);
    let done = false;
    const finish = v => { if (done) return; done = true; m.remove(); resolve(v); };
    m.querySelector('#reasonOk').onclick = () => {
      const v = m.querySelector('#reasonText').value.trim();
      if (!v) return toast('A reason is required.');
      finish(v);
    };
    m.querySelector('#reasonCancel').onclick = () => finish(null);
    m.querySelector('.modal-close').onclick = () => finish(null);
    m.addEventListener('click', e => { if (e.target === m) finish(null); });
  });
}

async function loadAssignPanel(m, t, id, reopen) {
  const panel = m.querySelector('#assignPanel');
  if (!panel) return;
  const reassign = !!t.assigned_to;
  let d;
  try { d = await api(`/api/tasks/${id}/assignment-options`); }
  catch (e) { panel.innerHTML = `<strong>${reassign ? 'Reassign' : 'Assign'}</strong><div class="muted small">Could not load suggestions: ${esc(e.message)}</div>`; return; }
  const fit = o => ({ match: 'Team match', no_team_required: 'Any team', different_team: 'Different team' })[o.compatibility];
  panel.innerHTML = `
    <strong>${reassign ? 'Reassign' : 'Assign'}</strong>
    <div class="muted small">${d.team ? `Category team: ${esc(d.team)}. ` : 'This category has no team, so any personnel qualifies. '}Active tasks are counted by the server.</div>
    ${d.note ? `<div class="muted small">${esc(d.note)}</div>` : ''}
    ${reassign ? '<input class="input" id="reassignReason" maxlength="500" placeholder="Reason for reassigning (required)" style="margin:8px 0">' : ''}
    <div class="table-wrap"><table class="table assign-table"><thead><tr><th>Person</th><th>Active tasks</th><th>Team fit</th><th></th></tr></thead><tbody>${
      d.options.map(o => `<tr>
        <td><strong>${esc(o.full_name)}</strong> ${o.suggested ? '<span class="badge badge-green">Suggested</span>' : ''}<br><span class="muted small">${esc(o.role)}${o.note ? ' · ' + esc(o.note) : ''}</span></td>
        <td>${o.active_tasks}</td><td>${fit(o)}</td>
        <td>${o.note === 'Current holder' ? '' : `<button class="btn small${o.suggested ? ' primary' : ''}" data-pick="${esc(o.id)}">${reassign ? 'Reassign' : 'Assign'}</button>`}</td></tr>`).join('')
    }</tbody></table></div>`;
  panel.querySelectorAll('[data-pick]').forEach(b => b.onclick = async () => {
    const body = { assignedTo: b.dataset.pick };
    if (reassign) {
      body.reason = panel.querySelector('#reassignReason').value.trim();
      if (!body.reason) return toast('Give a reason for the reassignment.');
    }
    try {
      await api(`/api/tasks/${id}/${reassign ? 'reassign' : 'assign'}`, { method: 'POST', body: JSON.stringify(body) });
      toast(reassign ? 'Task reassigned.' : 'Task assigned.'); reopen();
    } catch (e) { toast(e.message); }
  });
}
