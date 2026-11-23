// --- New Request ---
async function newRequest(c) {
  setHeader('New Request');
  c.innerHTML = `
    <div class="card">
      <div class="card-title">
        <h3>Request details</h3>
        <span class="small muted">Fields marked <span class="req">*</span> are required</span>
      </div>
      <div class="form-error" id="newFormError" role="alert"></div>
      <form id="newForm" class="form-grid" novalidate>
        <div class="form-section">
          <h4>What do you need?</h4>
          <div class="form-grid">
            <div class="form-field full-span">
              <label for="fTitle">Request title <span class="req" aria-hidden="true">*</span></label>
              <input class="input" id="fTitle" maxlength="160" required placeholder="e.g. Printer repair, Registrar Room 3"
                     aria-describedby="fTitleHint fTitleError">
              <span class="form-help" id="fTitleHint">A short summary of the problem or service you need.</span>
              <span class="field-error" id="fTitleError" role="alert"></span>
            </div>
            <div class="form-field">
              <label for="fCategory">Category <span class="req" aria-hidden="true">*</span></label>
              <select class="select" id="fCategory" required aria-describedby="fCategoryHint fCategoryError">
                <option value="">Loading categories…</option>
              </select>
              <span class="form-help" id="fCategoryHint" aria-live="polite"></span>
              <span class="field-error" id="fCategoryError" role="alert"></span>
            </div>
            <div class="form-field">
              <label for="fPriority">Priority</label>
              <select class="select" id="fPriority">
                <option value="low">Low</option>
                <option value="medium" selected>Medium</option>
                <option value="high">High</option>
              </select>
              <span class="form-help">Choose how soon this needs attention.</span>
            </div>
            <div class="form-field">
              <label for="fDeadline">Preferred deadline <span class="muted">(optional)</span></label>
              <input class="input" id="fDeadline" type="datetime-local" aria-describedby="fDeadlineHint">
              <span class="form-help" id="fDeadlineHint">The category SLA sets the official due date.</span>
            </div>
          </div>
        </div>

        <div class="form-section">
          <h4>Where and what</h4>
          <div class="form-grid">
            <div class="form-field full-span">
              <label for="fLocation">Location <span class="muted">(optional)</span></label>
              <input class="input" id="fLocation" maxlength="255" placeholder="e.g. Registrar Office, Room 3"
                     aria-describedby="fLocationHint">
              <span class="form-help" id="fLocationHint">Where should the team go, if applicable?</span>
            </div>
            <div class="form-field full-span">
              <label for="fDescription">Description <span class="req" aria-hidden="true">*</span></label>
              <textarea class="textarea" id="fDescription" required
                        placeholder="Describe what happened, what you already tried, and what outcome you expect."
                        aria-describedby="fDescriptionHint fDescriptionError"></textarea>
              <span class="form-help" id="fDescriptionHint">Include enough detail for the team to understand the request.</span>
              <span class="field-error" id="fDescriptionError" role="alert"></span>
            </div>
          </div>
        </div>

        <div class="form-section">
          <h4>Attachments</h4>
          <div class="form-grid">
            <div class="form-field full-span">
              <label for="fFiles">Attach files <span class="muted">(optional)</span></label>
              <input type="file" id="fFiles" multiple
                     accept=".jpg,.jpeg,.png,.gif,.webp,.pdf,.txt,.doc,.docx,.xls,.xlsx,.csv"
                     aria-describedby="fFilesHint fFilesError">
              <span class="form-help" id="fFilesHint">Up to 5 files, 5 MB each: images, PDF, text, Word, Excel or CSV.</span>
              <span class="field-error" id="fFilesError" role="alert"></span>
            </div>
          </div>
        </div>

        <div class="form-actions full-span">
          <button type="button" class="btn" id="cancelNew">Cancel</button>
          <button type="submit" class="btn primary" id="submitNew">Submit request</button>
        </div>
      </form>
    </div>`;

  let categories = [];
  try {
    categories = (await api('/api/categories')).categories;
    $('#fCategory').innerHTML = categories.map(x => `<option value="${esc(x.name)}">${esc(x.name)}</option>`).join('');
  } catch (e) {
    $('#fCategory').innerHTML = '<option value="">Categories unavailable</option>';
    $('#fCategoryHint').textContent = 'Reload the page or contact an administrator if this continues.';
    toast(e.message);
  }

  const showCategoryHint = () => {
    if (!categories.length) return;
    const x = categories.find(k => k.name === $('#fCategory').value);
    $('#fCategoryHint').textContent = x
      ? `Expected within ${hoursLabel(x.default_sla_hours)}${x.team ? ` · handled by ${x.team}` : ''}`
      : '';
  };
  $('#fCategory').onchange = showCategoryHint;
  showCategoryHint();

  const setFieldError = (id, message) => {
    const field = $('#' + id);
    const error = $('#' + id + 'Error');
    if (error) error.textContent = message || '';
    if (field) {
      if (message) field.setAttribute('aria-invalid', 'true');
      else field.removeAttribute('aria-invalid');
    }
  };

  const setFormError = (message) => {
    const box = $('#newFormError');
    if (box) box.textContent = message || '';
  };

  const clearOnEdit = (id) => {
    const field = $('#' + id);
    if (!field) return;
    const clear = () => { setFieldError(id, ''); setFormError(''); };
    field.addEventListener('input', clear);
    field.addEventListener('change', clear);
  };
  ['fTitle', 'fCategory', 'fDescription', 'fFiles'].forEach(clearOnEdit);

  const validate = () => {
    const title = $('#fTitle').value.trim();
    const category = $('#fCategory').value;
    const description = $('#fDescription').value.trim();
    const files = [...$('#fFiles').files];
    let firstInvalid = null;

    const check = (id, valid, message) => {
      if (valid) {
        setFieldError(id, '');
      } else {
        setFieldError(id, message);
        if (!firstInvalid) firstInvalid = $('#' + id);
      }
    };

    check('fTitle', !!title, 'Enter a short title for the request.');
    check('fCategory', !!category, categories.length ? 'Choose a category.' : 'Categories could not be loaded. Reload the page and try again.');
    check('fDescription', !!description, 'Describe what needs to be done.');

    if (files.length > 5) {
      check('fFiles', false, 'Attach at most 5 files.');
    } else {
      const badFile = files.find(f =>
        !ATTACH_TYPES.includes((f.name.match(/\.[^.]+$/) || [''])[0].toLowerCase()) ||
        f.size > 5 * 1024 * 1024 ||
        f.size === 0
      );
      check('fFiles', !badFile, badFile
        ? `${badFile.name}: only images, PDF, text, Word, Excel or CSV files up to 5 MB can be attached.`
        : '');
    }

    if (firstInvalid) {
      firstInvalid.focus();
      return false;
    }
    setFormError('');
    return true;
  };

  $('#cancelNew').onclick = () => { state.page = 'dashboard'; render(); };
  $('#newForm').onsubmit = async e => {
    e.preventDefault();
    if (!validate()) return;

    const submit = $('#submitNew');
    const files = [...$('#fFiles').files];
    submit.disabled = true;
    submit.textContent = 'Submitting…';
    try {
      const fd = new FormData();
      fd.append('payload', JSON.stringify({
        title: $('#fTitle').value.trim(),
        category: $('#fCategory').value,
        priority: $('#fPriority').value,
        deadline: $('#fDeadline').value ? new Date($('#fDeadline').value).toISOString() : null,
        location: $('#fLocation').value.trim(),
        description: $('#fDescription').value.trim()
      }));
      files.forEach(f => fd.append('files', f));
      const d = await api('/api/tasks', { method: 'POST', body: fd });
      toast(`${d.taskCode} created successfully.`);
      state.page = 'tasks';
      await render();
      openTask(d.taskId);
    } catch (x) {
      setFormError(x.message || 'Could not submit the request. Check the fields and try again.');
      toast(x.message || 'Could not submit the request.');
    } finally {
      submit.disabled = false;
      submit.textContent = 'Submit request';
    }
  };
}
