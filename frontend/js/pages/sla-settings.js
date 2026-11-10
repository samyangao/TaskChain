async function slaPage(c) {
  setHeader('SLA Settings', 'Administration');
  const d = await api('/api/categories?all=1');
  const autoDays = (await api('/api/settings')).auto_close_days;
  const admin = state.user.role === 'administrator';
  c.innerHTML = `
    <div class="card">
      <div class="card-title"><h3>Service levels by category</h3>${admin ? '<button class="btn primary" id="addCat">Add category</button>' : ''}</div>
      <p class="muted small">The SLA clock starts when a request is submitted. A task is flagged overdue at its deadline and escalated to coordinators once the escalation time has passed. Changes apply to new tasks only.</p>
      ${d.categories.length ? `<div class="table-wrap"><table class="table"><thead><tr><th>Category</th><th>Default SLA</th><th>Escalation</th><th>Team</th><th>Status</th>${admin ? '<th></th>' : ''}</tr></thead><tbody>${
        d.categories.map(k => `<tr><td><strong>${esc(k.name)}</strong><br><span class="muted small">${esc(k.description)}</span></td>
          <td>${hoursLabel(k.default_sla_hours)}</td><td>${hoursLabel(k.escalation_hours)} after due</td><td>${esc(k.team || '—')}</td>
          <td>${k.is_active ? '<span class="badge badge-green">Active</span>' : '<span class="badge badge-gray">Inactive</span>'}</td>
          ${admin ? `<td><button class="btn small" data-edit="${k.id}">Edit</button></td>` : ''}</tr>`).join('')}</tbody></table></div>` : empty('No categories yet.')}
    </div>
    ${admin ? `<div class="card" style="margin-top:16px"><div class="card-title"><h3>Run the SLA check now</h3><button class="btn" id="runSla">Run check</button></div>
      <p class="muted small">The check also runs by itself about once a minute while the server is running.</p></div>` : ''}
    <div class="card" style="margin-top:16px"><div class="card-title"><h3>Completed requests</h3></div>
      <p class="muted small">When the work is finished, the requester confirms it or reopens it. If they do not respond, the request closes itself after this many days. Use 0 to never close automatically.</p>
      ${admin ? `<div class="form-actions" style="justify-content:flex-start"><input class="input" id="autoDays" type="number" min="0" max="365" step="1" style="max-width:120px" value="${autoDays}" aria-label="Days before a completed request closes automatically"><span class="muted">days</span><button class="btn primary" id="saveAuto">Save</button></div>`
        : `<div><strong>${autoDays === 0 ? 'Never closes automatically' : `${autoDays} day${autoDays === 1 ? '' : 's'}`}</strong></div>`}
    </div>`;
  if (!admin) return;
  $('#saveAuto').onclick = async () => {
    const days = parseInt($('#autoDays').value, 10);
    if (Number.isNaN(days) || days < 0 || days > 365) return toast('Enter a whole number of days from 0 to 365.');
    try { const r = await api('/api/settings', { method: 'PUT', body: JSON.stringify({ auto_close_days: days }) }); toast(r.message); }
    catch (e) { toast(e.message); }
  };
  $('#addCat').onclick = () => categoryModal(null);
  c.querySelectorAll('[data-edit]').forEach(b => b.onclick = () => categoryModal(d.categories.find(k => k.id === b.dataset.edit)));
  $('#runSla').onclick = async () => {
    try {
      const r = await api('/api/sla/run', { method: 'POST' });
      toast(r.skipped ? 'Another check is already running.' : `Checked: ${r.warned} warned, ${r.overdue} overdue, ${r.escalated} escalated, ${r.auto_closed} auto-closed.`);
    } catch (e) { toast(e.message); }
  };
}

function categoryModal(cat) {
  const editing = !!cat;
  const m = openModal(`
    <div class="modal-head"><div><div class="eyebrow">SLA Settings</div><h2>${editing ? 'Edit category' : 'Add category'}</h2></div><button class="modal-close" aria-label="Close">×</button></div>
    <div class="form-grid">
      <div class="form-field full-span"><label>Name</label><input class="input" id="cName" maxlength="80" value="${esc(cat ? cat.name : '')}" ${editing ? 'disabled' : ''}>
        ${editing ? '<span class="small muted">A category name cannot be changed. Add a new one and deactivate this one instead.</span>' : ''}</div>
      <div class="form-field full-span"><label>Description</label><input class="input" id="cDesc" maxlength="255" value="${esc(cat ? cat.description : '')}"></div>
      <div class="form-field"><label>Default SLA (hours)</label><input class="input" id="cSla" type="number" min="1" max="8760" step="1" value="${cat ? cat.default_sla_hours : 48}"><span class="small muted" id="cSlaHint"></span></div>
      <div class="form-field"><label>Escalate after due (hours)</label><input class="input" id="cEsc" type="number" min="0" max="8760" step="1" value="${cat ? cat.escalation_hours : 24}"><span class="small muted" id="cEscHint"></span></div>
      <div class="form-field full-span"><label>Assigned team</label><input class="input" id="cTeam" maxlength="80" value="${esc(cat ? cat.team : '')}"></div>
      <label class="pref-row full-span"><input type="checkbox" id="cActive" ${(!cat || cat.is_active) ? 'checked' : ''}><span><strong>Active</strong><br><span class="muted small">Inactive categories cannot be chosen on new requests.</span></span></label>
      <div class="form-actions full-span"><button class="btn primary" id="cSave">Save</button></div>
    </div>`);
  const hint = () => {
    const s = parseInt(m.querySelector('#cSla').value, 10), e = parseInt(m.querySelector('#cEsc').value, 10);
    m.querySelector('#cSlaHint').textContent = s > 0 ? `= ${hoursLabel(s)}` : '';
    m.querySelector('#cEscHint').textContent = e >= 0 ? `= ${hoursLabel(e)}` : '';
  };
  m.querySelector('#cSla').oninput = hint; m.querySelector('#cEsc').oninput = hint; hint();
  m.querySelector('#cSave').onclick = async () => {
    const body = {
      description: m.querySelector('#cDesc').value,
      default_sla_hours: parseInt(m.querySelector('#cSla').value, 10),
      escalation_hours: parseInt(m.querySelector('#cEsc').value, 10),
      team: m.querySelector('#cTeam').value,
      is_active: m.querySelector('#cActive').checked
    };
    if (!editing) body.name = m.querySelector('#cName').value;
    try {
      const r = await api(editing ? `/api/categories/${cat.id}` : '/api/categories', { method: editing ? 'PUT' : 'POST', body: JSON.stringify(body) });
      m.remove(); toast(r.message); render();
    } catch (e) { toast(e.message); }
  };
}
