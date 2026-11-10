async function usersPage(c) {
  setHeader('Users');
  const d = await api('/api/users');
  const admin = state.user.role === 'administrator';
  const roles = ['requester', 'coordinator', 'personnel', 'verifier', 'administrator'];
  c.innerHTML = `<div class="card"><div class="table-wrap"><table class="table"><thead><tr><th>Name</th><th>Email</th><th>Role</th><th>Teams</th><th>Active</th><th>Last login</th></tr></thead><tbody>${
    d.users.map(u => `<tr><td>${esc(u.full_name)}</td><td>${esc(u.email)}</td>
      <td>${admin && u.id !== state.user.id ? `<select class="select" data-uid="${u.id}" data-f="role">${roles.map(r => `<option ${r === u.role ? 'selected' : ''}>${r}</option>`).join('')}</select>` : esc(u.role)}</td>
      <td>${u.teams.length ? u.teams.map(t => `<span class="badge badge-gray">${esc(t)}</span>`).join(' ') : '<span class="muted">—</span>'}${admin ? ` <button class="btn small" data-teams-for="${u.id}">Edit</button>` : ''}</td>
      <td>${admin && u.id !== state.user.id ? `<input type="checkbox" data-uid="${u.id}" data-f="active" ${u.is_active ? 'checked' : ''}>` : (u.is_active ? 'Yes' : 'No')}</td>
      <td>${fmt(u.last_login_at)}</td></tr>`).join('')}</tbody></table></div></div>`;
  c.querySelectorAll('[data-uid]').forEach(el => el.onchange = async () => {
    const id = el.dataset.uid;
    const role = c.querySelector(`[data-uid="${id}"][data-f="role"]`).value;
    const isActive = c.querySelector(`[data-uid="${id}"][data-f="active"]`).checked;
    try { await api('/api/users/' + id, { method: 'PATCH', body: JSON.stringify({ role, isActive }) }); toast('User updated.'); }
    catch (e) { toast(e.message); render(); }
  });
  c.querySelectorAll('[data-teams-for]').forEach(b => b.onclick = () => teamsModal(d.users.find(u => u.id === b.dataset.teamsFor)));
}

async function teamsModal(u) {
  let teams;
  try { teams = (await api('/api/teams')).teams; } catch (e) { return toast(e.message); }
  const m = openModal(`
    <div class="modal-head"><div><div class="eyebrow">Teams</div><h2>${esc(u.full_name)}</h2></div><button class="modal-close" aria-label="Close">×</button></div>
    <p class="muted small">Only members of a category's team are suggested for its tasks. Teams come from the categories under SLA Settings.</p>
    ${teams.length ? teams.map(t => `<label class="pref-row"><input type="checkbox" data-team="${esc(t.name)}" ${u.teams.some(x => x.toLowerCase() === t.name.toLowerCase()) ? 'checked' : ''}>
      <span><strong>${esc(t.name)}</strong><br><span class="muted small">${t.member_count} member${t.member_count === 1 ? '' : 's'}</span></span></label>`).join('')
      : empty('No teams yet. Give a category a team under SLA Settings first.')}
    <div class="form-actions"><button class="btn primary" id="teamsSave"${teams.length ? '' : ' disabled'}>Save</button></div>`);
  m.querySelector('#teamsSave').onclick = async () => {
    const chosen = [...m.querySelectorAll('[data-team]')].filter(x => x.checked).map(x => x.dataset.team);
    try { await api(`/api/users/${u.id}/teams`, { method: 'PUT', body: JSON.stringify({ teams: chosen }) }); m.remove(); toast('Teams saved.'); render(); }
    catch (e) { toast(e.message); }
  };
}
