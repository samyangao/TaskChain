async function usersPage(c) {
  setHeader('Users');
  const d = await api('/api/users');
  state.users = d.users;
  const admin = state.user.role === 'administrator';
  const roles = ['requester', 'coordinator', 'personnel', 'verifier', 'administrator'];
  const active = d.users.filter(u => u.is_active).length;
  const admins = d.users.filter(u => u.role === 'administrator').length;
  const coordinators = d.users.filter(u => u.role === 'coordinator').length;

  c.innerHTML = `
    <div class="grid stats">
      <div class="stat"><div class="stat-icon" aria-hidden="true">${ICONS.users}</div><div class="label">Total users</div><div class="num">${d.users.length}</div><div class="sub">All accounts</div></div>
      <div class="stat completed"><div class="stat-icon" aria-hidden="true">${ICONS.done}</div><div class="label">Active</div><div class="num">${active}</div><div class="sub">Can sign in</div></div>
      <div class="stat"><div class="stat-icon" aria-hidden="true">${ICONS.security}</div><div class="label">Administrators</div><div class="num">${admins}</div><div class="sub">Full access</div></div>
      <div class="stat attention"><div class="stat-icon" aria-hidden="true">${ICONS.tasks}</div><div class="label">Coordinators</div><div class="num">${coordinators}</div><div class="sub">Manage requests</div></div>
    </div>
    <div class="toolbar">
      <input class="input search" id="userSearch" placeholder="Search name, email, role or team…">
      <select class="select" id="userRoleFilter"><option value="">All roles</option>${roles.map(r => `<option value="${r}">${r[0].toUpperCase() + r.slice(1)}</option>`).join('')}</select>
      <select class="select" id="userActiveFilter"><option value="">All accounts</option><option value="active">Active</option><option value="inactive">Inactive</option></select>
    </div>
    <div class="toolbar-meta"><span id="userCount" class="small muted"></span></div>
    <div class="card" id="usersCard"></div>`;

  const renderRows = () => {
    const q = ($('#userSearch')?.value || '').toLowerCase();
    const role = $('#userRoleFilter')?.value || '';
    const status = $('#userActiveFilter')?.value || '';
    const rows = d.users.filter(u =>
      (!role || u.role === role) &&
      (!status || (status === 'active' ? u.is_active : !u.is_active)) &&
      (!q || [u.full_name, u.email, u.role, ...(u.teams || [])].join(' ').toLowerCase().includes(q))
    );

    const card = $('#usersCard');
    if (card) {
      card.innerHTML = rows.length
        ? `<div class="table-wrap"><table class="table"><thead><tr><th>Name</th><th>Email</th><th>Role</th><th>Teams</th><th>Active</th><th>Last login</th></tr></thead><tbody>${rows.map(u => userRowHtml(u, admin, roles)).join('')}</tbody></table></div>`
        : empty('No users match these filters.', '<button class="btn small" id="clearUserFilters">Clear filters</button>');
    }
    const count = $('#userCount');
    if (count) count.textContent = `${rows.length} account${rows.length === 1 ? '' : 's'}`;

    const clear = $('#clearUserFilters');
    if (clear) clear.onclick = clearUserFilters;

    c.querySelectorAll('[data-uid]').forEach(el => el.onchange = async () => {
      const id = el.dataset.uid;
      const roleValue = c.querySelector(`[data-uid="${id}"][data-f="role"]`).value;
      const isActive = c.querySelector(`[data-uid="${id}"][data-f="active"]`).checked;
      try {
        await api('/api/users/' + id, { method: 'PATCH', body: JSON.stringify({ role: roleValue, isActive }) });
        toast('User updated.');
        await render();
      } catch (e) {
        toast(e.message);
        render();
      }
    });
    c.querySelectorAll('[data-teams-for]').forEach(b => b.onclick = () => teamsModal(d.users.find(u => u.id === b.dataset.teamsFor)));
  };

  const clearUserFilters = () => {
    ['userSearch', 'userRoleFilter', 'userActiveFilter'].forEach(id => {
      const el = $('#' + id);
      if (el) el.value = '';
    });
    renderRows();
  };

  $('#userSearch').oninput = renderRows;
  $('#userRoleFilter').onchange = renderRows;
  $('#userActiveFilter').onchange = renderRows;
  renderRows();
}

function userRowHtml(u, admin, roles) {
  const teams = (u.teams || []).length
    ? u.teams.map(t => `<span class="badge badge-gray">${esc(t)}</span>`).join(' ')
    : '<span class="muted">—</span>';
  return `<tr>
    <td>${esc(u.full_name)}</td>
    <td>${esc(u.email)}</td>
    <td>${admin && u.id !== state.user.id ? `<select class="select" data-uid="${u.id}" data-f="role" aria-label="Role for ${esc(u.full_name)}">${roles.map(r => `<option ${r === u.role ? 'selected' : ''}>${r}</option>`).join('')}</select>` : esc(u.role)}</td>
    <td>${teams}${admin ? ` <button class="btn small" data-teams-for="${u.id}" aria-label="Edit teams for ${esc(u.full_name)}">Edit</button>` : ''}</td>
    <td>${admin && u.id !== state.user.id ? `<input type="checkbox" data-uid="${u.id}" data-f="active" aria-label="Account active for ${esc(u.full_name)}" ${u.is_active ? 'checked' : ''}>` : (u.is_active ? 'Yes' : 'No')}</td>
    <td>${fmt(u.last_login_at)}</td>
  </tr>`;
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
