// ==========================================
// 7. MISSING PAGES (were called by renderPage but never defined)
// ==========================================
const isManager = () => ['administrator', 'coordinator'].includes(state.user.role);
const canEditCollab = t => isManager() || [t.created_by, t.assigned_to].includes(state.user.id);
const roleBadge = role => `<span class="role-badge role-${esc(role)}">${esc(role)}</span>`;
const depStateLabel = s => s === 'for_verification' ? 'For verification or later' : 'Completed';
function linkifyMentions(text, names = []) {
  let out = esc(text);
  (names || []).forEach(name => {
    if (!name) return;
    const safe = esc(name).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    out = out.replace(new RegExp('@' + safe, 'g'), `<span class="mention">@${esc(name)}</span>`);
  });
  return out;
}

function subtaskSectionHtml(d, t, canEdit) {
  const total = d.subtasks.length;
  const done = d.subtasks.filter(s => s.is_done).length;
  const pct = total ? Math.round(done / total * 100) : 0;
  return `<h3>Checklist <span class="muted small">${done} / ${total} completed</span></h3>
    <div class="subtask-progress" aria-label="${done} of ${total} subtasks completed">
      <div class="subtask-bar"><i style="width:${pct}%"></i></div><span>${done} / ${total}</span>
    </div>
    ${total ? `<div class="subtask-list">${d.subtasks.map(s => `<div class="subtask ${s.is_done ? 'is-done' : ''}">
      <label><input type="checkbox" data-subtask-toggle="${s.id}" ${s.is_done ? 'checked' : ''} ${canEdit ? '' : 'disabled'}>
      <span>${esc(s.title)}</span></label>
      <span class="muted small">${s.is_done && s.done_by_name ? `done by ${esc(s.done_by_name)}` : ''}</span>
      ${canEdit ? `<button class="icon-btn" data-subtask-delete="${s.id}" title="Remove subtask" aria-label="Remove subtask">×</button>` : ''}
    </div>`).join('')}</div>` : empty('No checklist items yet.')}
    ${canEdit ? `<div class="inline-form"><input class="input" id="subtaskTitle" maxlength="160" placeholder="Add a step (for example, collect documents)"><button class="btn small" id="addSubtask">Add</button></div>` : ''}`;
}

function dependencySectionHtml(d, t, canEdit) {
  const unmet = d.dependencies.filter(x => !x.met);
  return `<h3>Dependencies <span class="muted small">${d.dependencies.length} upstream</span></h3>
    ${unmet.length ? `<div class="notice blocked-notice"><strong>Blocked.</strong> Waiting for ${unmet.map(x => `<span class="badge badge-red">${esc(x.task_code)}</span>`).join(' ')} to reach ${unmet.map(x => esc(depStateLabel(x.required_state))).join(' or ')}.</div>` : ''}
    ${d.dependencies.length ? `<div class="dep-list">${d.dependencies.map(x => `<div class="dep-row">
      <div><strong>${esc(x.task_code)}</strong> <span class="muted">${esc(x.title)}</span><br><span class="small muted">Needs ${esc(depStateLabel(x.required_state))}</span></div>
      ${x.met ? '<span class="badge badge-green">Met</span>' : '<span class="badge badge-red">Waiting</span>'}
      ${canEdit ? `<button class="icon-btn" data-dep-delete="${x.depends_on_id}" title="Remove dependency" aria-label="Remove dependency">×</button>` : ''}
    </div>`).join('')}</div>` : empty('This task does not wait for another task.')}
    ${d.dependents.length ? `<div class="small muted" style="margin-top:8px">Tasks waiting on this one: ${d.dependents.map(x => `<strong>${esc(x.task_code)}</strong> (${esc(depStateLabel(x.required_state))})`).join(' · ')}</div>` : ''}
    ${canEdit ? `<div class="dep-add"><div class="inline-form">
      <select class="select" id="depSelect"><option value="">Loading tasks…</option></select>
      <select class="select" id="depState"><option value="completed">Completed</option><option value="for_verification">For verification or later</option></select>
      <button class="btn small" id="addDep" type="button">Add dependency</button>
    </div></div>` : ''}`;
}

function watchersHtml(d) {
  return `<h3>Watchers <span class="muted small">${d.watchers.length}</span></h3>
    ${d.watchers.length ? `<div class="chip-row">${d.watchers.map(w => `<span class="chip">${esc(w.full_name)} ${roleBadge(w.role)}</span>`).join('')}</div>` : empty('No one is watching yet.')}`;
}

function commentsHtml(d) {
  return `<h3>Comments <span class="muted small">${d.comments.length}</span></h3>
    ${d.comments.length ? `<div class="comment-list">${d.comments.map(c => `<div class="comment">
      <div class="comment-head"><strong>${esc(c.author_name)}</strong> ${roleBadge(c.author_role)} <span class="muted small">${fmt(c.created_at)}</span></div>
      <div class="comment-body">${linkifyMentions(c.body, c.mention_names)}</div>
      ${(c.mention_names || []).length ? `<div class="small muted">Mentioned ${c.mention_names.map(n => `@${esc(n)}`).join(', ')}</div>` : ''}
    </div>`).join('')}</div>` : empty('No comments yet.')}
    <div class="comment-compose">
      <textarea class="textarea" id="cmtText" maxlength="2000" placeholder="Write a comment… use @ to mention someone"></textarea>
      <div class="comment-tools">
        <select class="select" id="mentionSelect"><option value="">@ Mention someone…</option>${d.mentionable.map(u => `<option value="${u.id}" data-name="${esc(u.full_name)}">${esc(u.full_name)} · ${esc(u.role)}</option>`).join('')}</select>
        <button class="btn small" id="mentionInsert" type="button">Insert mention</button>
        <button class="btn primary small" id="cmtBtn" type="button">Post comment</button>
      </div>
    </div>`;
}

async function loadDependencyOptions(m, id, d) {
  const select = m.querySelector('#depSelect');
  if (!select) return;
  try {
    const options = (await api(`/api/tasks/${id}/dependency-options`)).options;
    select.innerHTML = '<option value="">Choose a task…</option>' + options.map(o => `<option value="${o.id}">${esc(o.task_code)} · ${esc(o.title)} · ${esc(statusLabel(o.status))}</option>`).join('');
    if (!options.length) select.innerHTML = '<option value="">No eligible tasks</option>';
  } catch (e) {
    select.innerHTML = `<option value="">Could not load tasks</option>`;
    toast(e.message);
  }
}
