async function securityPage(c) {
  setHeader('Security', 'Account');
  const overview = await api('/api/security/overview');
  let adminData = null;
  if (state.user.role === 'administrator') {
    try { adminData = await api('/api/security/login-attempts'); } catch (e) { /* personal security still works */ }
  }
  const totpOn = !!overview.totp_enabled;
  let adminHtml = '';
  if (adminData) {
    const since = Date.now() - 24 * 3600 * 1000;
    const failed24 = adminData.attempts.filter(a => !a.success && new Date(a.attempted_at).getTime() > since).length;
    const lockedHtml = adminData.locked_accounts.length
      ? `<div class="table-wrap"><table class="table"><thead><tr><th>Account</th><th>Role</th><th>Failed attempts</th><th>Locked until</th></tr></thead><tbody>${
          adminData.locked_accounts.map(l => `<tr><td><strong>${esc(l.full_name)}</strong><br><span class="muted">${esc(l.email)}</span></td><td>${esc(l.role)}</td><td>${esc(l.failed_login_attempts)}</td><td>${fmt(l.locked_until)}</td></tr>`).join('')
        }</tbody></table></div>`
      : empty('No accounts are locked right now.');
    const attemptsHtml = adminData.attempts.length
      ? `<div class="table-wrap"><table class="table"><thead><tr><th>Time</th><th>Email</th><th>Account</th><th>IP</th><th>Result</th></tr></thead><tbody>${
          adminData.attempts.map(a => `<tr><td>${fmt(a.attempted_at)}</td><td>${esc(a.email)}</td><td>${esc(a.user_name)}</td><td>${esc(a.ip_address)}</td><td>${a.success ? '<span class="badge badge-green">Success</span>' : '<span class="badge badge-red">Failed</span>'}</td></tr>`).join('')
        }</tbody></table></div>`
      : empty('No login attempts recorded yet.');
    adminHtml = `
      <div class="grid stats" style="margin-top:18px">
        <div class="stat"><div class="label">Failed logins (24h)</div><div class="num">${failed24}</div></div>
        <div class="stat"><div class="label">Locked accounts now</div><div class="num">${adminData.locked_accounts.length}</div></div>
        <div class="stat"><div class="label">Recent attempts shown</div><div class="num">${adminData.attempts.length}</div></div>
      </div>
      <div class="card" style="margin-top:18px"><div class="card-title"><h3>Locked accounts</h3><span class="muted small">Administrator view</span></div>${lockedHtml}</div>
      <div class="card" style="margin-top:18px"><div class="card-title"><h3>Recent login attempts</h3><span class="muted small">Administrator view</span></div>${attemptsHtml}</div>`;
  }
  c.innerHTML = `
    <div class="security-grid">
      <div class="card security-card">
        <div class="security-card-head"><div class="security-icon">${ICONS.security}</div><div><h3>Password</h3><p class="muted small">Change the password used to sign in.</p></div></div>
        <div class="security-meta"><span class="muted small">Last changed</span><strong>${overview.password_changed_at ? fmt(overview.password_changed_at) : 'Not recorded'}</strong></div>
        <button class="btn" id="changePasswordBtn">Change password</button>
      </div>
      <div class="card security-card">
        <div class="security-card-head"><div class="security-icon ${totpOn ? 'is-on' : ''}">${ICONS.verification}</div><div><h3>Two-factor authentication</h3><p class="muted small">A 6-digit code from an authenticator app at sign-in.</p></div></div>
        <div class="security-meta"><span class="muted small">Status</span><strong>${totpOn ? '<span class="badge badge-green">Enabled</span>' : '<span class="badge badge-gray">Not set up</span>'}</strong></div>
        <button class="btn ${totpOn ? '' : 'primary'}" id="totpBtn">${totpOn ? 'Disable 2FA' : 'Set up 2FA'}</button>
      </div>
      <div class="card security-card">
        <div class="security-card-head"><div class="security-icon">${ICONS.users}</div><div><h3>Sessions</h3><p class="muted small">End every signed-in browser, including this one.</p></div></div>
        <div class="security-meta"><span class="muted small">This session started</span><strong>${overview.session_started_at ? fmt(overview.session_started_at) : '—'}</strong></div>
        <button class="btn danger" id="signOutEverywhereBtn">Sign out everywhere</button>
      </div>
    </div>
    <div class="notice security-note"><strong>Security tip.</strong> Use a unique password and keep your authenticator app on a device you control. If you suspect someone else has access, change your password and sign out everywhere.</div>
    ${adminHtml}`;
  c.querySelector('#changePasswordBtn').onclick = () => changePasswordModal();
  c.querySelector('#totpBtn').onclick = () => totpOn ? totpDisableModal() : totpSetupModal();
  c.querySelector('#signOutEverywhereBtn').onclick = async () => {
    if (!confirm('Sign out of TaskChain on every device? You will need to sign in again.')) return;
    try {
      await api('/api/security/sign-out-everywhere', { method: 'POST' });
      window.location.href = '/login.html';
    } catch (e) { toast(e.message); }
  };
}

function changePasswordModal() {
  const m = openModal(`
    <div class="modal-head"><div><div class="eyebrow">Account security</div><h2>Change password</h2></div><button class="modal-close" aria-label="Close">×</button></div>
    <div class="form-grid">
      <div class="form-field full-span"><label for="cpCurrent">Current password</label><input class="input" id="cpCurrent" type="password" autocomplete="current-password"></div>
      <div class="form-field"><label for="cpNew">New password</label><input class="input" id="cpNew" type="password" autocomplete="new-password"></div>
      <div class="form-field"><label for="cpConfirm">Confirm new password</label><input class="input" id="cpConfirm" type="password" autocomplete="new-password"></div>
      <div class="form-actions full-span"><button class="btn" id="cpCancel">Cancel</button><button class="btn primary" id="cpSave">Change password</button></div>
    </div>`);
  m.querySelector('#cpCancel').onclick = () => m.remove();
  m.querySelector('#cpSave').onclick = async () => {
    const currentPassword = m.querySelector('#cpCurrent').value;
    const newPassword = m.querySelector('#cpNew').value;
    const confirmPassword = m.querySelector('#cpConfirm').value;
    if (!currentPassword || !newPassword) return toast('Enter your current and new password.');
    if (newPassword !== confirmPassword) return toast('The new passwords do not match.');
    const btn = m.querySelector('#cpSave'); btn.disabled = true;
    try {
      const r = await api('/api/security/password', { method: 'POST', body: JSON.stringify({ currentPassword, newPassword, confirmPassword }) });
      toast(r.message); m.remove(); render();
    } catch (e) { toast(e.message); btn.disabled = false; }
  };
}

function totpSetupModal() {
  const m = openModal(`
    <div class="modal-head"><div><div class="eyebrow">Account security</div><h2>Set up two-factor authentication</h2></div><button class="modal-close" aria-label="Close">×</button></div>
    <div id="totpSetupBody">
      <p class="muted small">Confirm your password to generate a new authenticator secret. The secret is shown only during setup.</p>
      <div class="form-field"><label for="totpPassword">Current password</label><input class="input" id="totpPassword" type="password" autocomplete="current-password"></div>
      <div class="form-actions"><button class="btn" id="totpCancel">Cancel</button><button class="btn primary" id="totpStart">Continue</button></div>
    </div>`);
  m.querySelector('#totpCancel').onclick = () => m.remove();
  m.querySelector('#totpStart').onclick = async () => {
    const password = m.querySelector('#totpPassword').value;
    if (!password) return toast('Enter your password.');
    const btn = m.querySelector('#totpStart'); btn.disabled = true;
    try {
      const d = await api('/api/security/totp/setup', { method: 'POST', body: JSON.stringify({ password }) });
      m.querySelector('#totpSetupBody').innerHTML = `
        <p class="muted small">Scan this QR code with Google Authenticator, Microsoft Authenticator, 1Password or another TOTP app.</p>
        <div class="totp-setup-grid">
          <div id="totpQr" class="totp-qr" aria-label="QR code for authenticator setup"></div>
          <div>
            <div class="form-field"><label>Manual setup key</label><code class="totp-secret">${esc(d.secret)}</code></div>
            <div class="form-field"><label for="totpEnableCode">6-digit code from the app</label><input class="input totp-code-input" id="totpEnableCode" inputmode="numeric" maxlength="6" autocomplete="one-time-code" placeholder="000000"></div>
            <div class="form-actions"><button class="btn" id="totpCancel2">Cancel</button><button class="btn primary" id="totpEnable">Enable 2FA</button></div>
          </div>
        </div>`;
      try {
        const qr = qrcode(0, 'M');
        qr.addData(d.otpauthUri); qr.make();
        m.querySelector('#totpQr').innerHTML = qr.createSvgTag({ cellSize: 4, margin: 2 });
      } catch (e) {
        m.querySelector('#totpQr').innerHTML = '<span class="muted small">QR unavailable — enter the key manually.</span>';
      }
      m.querySelector('#totpCancel2').onclick = () => m.remove();
      m.querySelector('#totpEnable').onclick = async () => {
        const code = m.querySelector('#totpEnableCode').value.replace(/\s/g, '');
        if (!/^\d{6}$/.test(code)) return toast('Enter the 6-digit code from your authenticator app.');
        const enableBtn = m.querySelector('#totpEnable'); enableBtn.disabled = true;
        try {
          const r = await api('/api/security/totp/enable', { method: 'POST', body: JSON.stringify({ code }) });
          toast(r.message); m.remove(); render();
        } catch (e) { toast(e.message); enableBtn.disabled = false; }
      };
    } catch (e) { toast(e.message); btn.disabled = false; }
  };
}

function totpDisableModal() {
  const m = openModal(`
    <div class="modal-head"><div><div class="eyebrow">Account security</div><h2>Disable two-factor authentication</h2></div><button class="modal-close" aria-label="Close">×</button></div>
    <p class="muted small">Confirm your password and a current authenticator code. Your other sessions will be signed out.</p>
    <div class="form-grid">
      <div class="form-field full-span"><label for="tdPassword">Current password</label><input class="input" id="tdPassword" type="password" autocomplete="current-password"></div>
      <div class="form-field full-span"><label for="tdCode">6-digit code</label><input class="input totp-code-input" id="tdCode" inputmode="numeric" maxlength="6" autocomplete="one-time-code" placeholder="000000"></div>
      <div class="form-actions full-span"><button class="btn" id="tdCancel">Cancel</button><button class="btn danger" id="tdDisable">Disable 2FA</button></div>
    </div>`);
  m.querySelector('#tdCancel').onclick = () => m.remove();
  m.querySelector('#tdDisable').onclick = async () => {
    const password = m.querySelector('#tdPassword').value;
    const code = m.querySelector('#tdCode').value.replace(/\s/g, '');
    if (!password || !/^\d{6}$/.test(code)) return toast('Enter your password and the 6-digit code.');
    const btn = m.querySelector('#tdDisable'); btn.disabled = true;
    try {
      const r = await api('/api/security/totp/disable', { method: 'POST', body: JSON.stringify({ password, code }) });
      toast(r.message); m.remove(); render();
    } catch (e) { toast(e.message); btn.disabled = false; }
  };
}
