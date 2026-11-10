// --- New Request ---
async function newRequest(c) {
  setHeader('New Request');
  c.innerHTML = `
    <div class="card">
      <div class="card-title"><h3>Create a task request</h3></div>
      <form id="newForm" class="form-grid">
        <div class="form-field">
          <label>Request title</label>
          <input class="input" id="fTitle" maxlength="160" required placeholder="e.g. Computer repair">
        </div>
        <div class="form-field">
          <label>Category</label>
          <select class="select" id="fCategory"><option>Loading…</option></select>
          <span class="small muted" id="fCategoryHint"></span>
        </div>
        <div class="form-field">
          <label>Priority</label>
          <select class="select" id="fPriority">
            <option value="low">Low</option><option value="medium" selected>Medium</option><option value="high">High</option>
          </select>
        </div>
        <div class="form-field"><label>Preferred deadline (optional)</label><input class="input" id="fDeadline" type="datetime-local"></div>
        <div class="form-field full-span"><label>Location</label><input class="input" id="fLocation"></div>
        <div class="form-field full-span">
          <label>Description</label>
          <textarea class="textarea" id="fDescription" required></textarea>
        </div>
        <div class="form-field full-span">
          <label>Attachments (optional)</label>
          <input type="file" id="fFiles" multiple accept=".jpg,.jpeg,.png,.gif,.webp,.pdf,.txt,.doc,.docx,.xls,.xlsx,.csv">
          <span class="small muted">Up to 5 files, 5 MB each: images, PDF, text, Word, Excel or CSV. The file type is checked on the server.</span>
        </div>
        <div class="form-actions full-span">
          <button type="button" class="btn" id="cancelNew">Cancel</button>
          <button class="btn primary">Submit request</button>
        </div>
      </form>
    </div>`;
    
  let categories = [];
  try {
    categories = (await api('/api/categories')).categories;
    $('#fCategory').innerHTML = categories.map(x => `<option>${esc(x.name)}</option>`).join('');
  } catch (e) { $('#fCategory').innerHTML = '<option value="">Could not load categories</option>'; toast(e.message); }
  const showHint = () => {
    const x = categories.find(k => k.name === $('#fCategory').value);
    $('#fCategoryHint').textContent = x ? `Expected within ${hoursLabel(x.default_sla_hours)}${x.team ? ` · handled by ${x.team}` : ''}` : '';
  };
  $('#fCategory').onchange = showHint;
  showHint();
  $('#cancelNew').onclick = () => { state.page = 'dashboard'; render(); };
  $('#newForm').onsubmit = async e => {
    e.preventDefault();
    const files = [...$('#fFiles').files];
    const badFile = files.find(f => !ATTACH_TYPES.includes((f.name.match(/\.[^.]+$/) || [''])[0].toLowerCase()) || f.size > 5 * 1024 * 1024 || f.size === 0);
    if (files.length > 5) return toast('Attach at most 5 files.');
    if (badFile) return toast(`${badFile.name}: only images, PDF, text, Word, Excel or CSV files up to 5 MB can be attached.`);
    try {
      const fd = new FormData();
      fd.append('payload', JSON.stringify({
        title: $('#fTitle').value,
        category: $('#fCategory').value,
        priority: $('#fPriority').value,
        deadline: $('#fDeadline').value ? new Date($('#fDeadline').value).toISOString() : null,
        location: $('#fLocation').value,
        description: $('#fDescription').value
      }));
      files.forEach(f => fd.append('files', f));
      const d = await api('/api/tasks', { method: 'POST', body: fd });
      toast(`${d.taskCode} created successfully.`);
      state.page = 'tasks';
      await render();
      openTask(d.taskId);
    } catch (x) { toast(x.message); }
  };
}
