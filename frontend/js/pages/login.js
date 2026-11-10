// Two-step login: password + CAPTCHA, then email OTP. Server enforces lockout.
(() => {
  const $ = (s) => document.querySelector(s);
  const config = { forgotAfter: 2, otpExpiryMinutes: 3 };
  let failureCount = 0;
  let lockTimer = null;
  let resendTimer = null;
  let lockUntil = 0;

  const loginForm = $('#loginForm');
  const otpForm = $('#otpForm');
  const submitBtn = $('#submit');
  const registerLink = $('#registerLink');
  const forgotWrap = $('#forgotWrap');
  const lockoutBox = $('#lockout');

  function showAlert(message, type = 'error') {
    const box = $('#alert');
    $('#alertText').textContent = message;
    box.className = `alert show ${type}`;
    if (type === 'error') {
      box.classList.add('shake');
      setTimeout(() => box.classList.remove('shake'), 450);
    }
  }
  function hideAlert() { $('#alert').className = 'alert'; }
  function setError(id, message) { const el = $(`#error-${id}`); if (el) el.textContent = message || ''; }
  function clearErrors() { ['identifier', 'password', 'captcha', 'otp'].forEach((id) => setError(id, '')); }

  function refreshCaptcha() {
    const img = $('#captchaImage');
    if (img) img.src = `/api/captcha?t=${Date.now()}`;
    const input = $('#captcha');
    if (input) input.value = '';
  }

  function startLockout(seconds) {
    clearInterval(lockTimer);
    let left = Math.max(1, Number(seconds) || 0);
    lockUntil = Date.now() + left * 1000;
    submitBtn.disabled = true;
    registerLink.setAttribute('aria-disabled', 'true');
    registerLink.style.pointerEvents = 'none';
    registerLink.style.opacity = '0.45';
    lockoutBox.hidden = false;
    const tick = () => {
      lockoutBox.textContent = `Too many failed attempts. Try again in ${left}s.`;
      if (left <= 0) {
        clearInterval(lockTimer);
        submitBtn.disabled = false;
        registerLink.removeAttribute('aria-disabled');
        registerLink.style.pointerEvents = '';
        registerLink.style.opacity = '';
        lockoutBox.hidden = true;
        lockUntil = 0;
        return;
      }
      left -= 1;
    };
    tick();
    lockTimer = setInterval(tick, 1000);
  }

  function startResendCooldown(seconds = 60) {
    clearInterval(resendTimer);
    const button = $('#resend');
    let left = Math.max(1, Number(seconds) || 0);
    button.disabled = true;
    const tick = () => {
      button.textContent = left > 0 ? `Resend code in ${left}s` : 'Resend code';
      if (left <= 0) {
        clearInterval(resendTimer);
        button.disabled = false;
        return;
      }
      left -= 1;
    };
    tick();
    resendTimer = setInterval(tick, 1000);
  }

  async function loadConfig() {
    try {
      const response = await fetch('/api/security/config', { credentials: 'same-origin' });
      if (response.ok) Object.assign(config, await response.json());
    } catch (_) { /* keep seeded defaults */ }
  }

  $('#show').addEventListener('click', () => {
    const input = $('#password');
    const reveal = input.type === 'password';
    input.type = reveal ? 'text' : 'password';
    $('#show').textContent = reveal ? 'Hide' : 'Show';
    $('#show').setAttribute('aria-pressed', String(reveal));
  });

  $('#captchaRefresh').addEventListener('click', refreshCaptcha);

  loginForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    hideAlert();
    clearErrors();
    const identifier = $('#identifier').value.trim();
    const password = $('#password').value;
    if (!identifier) return setError('identifier', 'Enter your username or email.');
    if (!password) return setError('password', 'Enter your password.');
    if (!$('#captcha').value.trim()) return setError('captcha', 'Type the CAPTCHA characters.');

    submitBtn.disabled = true;
    $('#submitText').hidden = true;
    $('#submitSpinner').hidden = false;
    try {
      const response = await secureFetch('/api/login', {
        method: 'POST',
        body: JSON.stringify({
          identifier,
          password,
          captcha: $('#captcha').value.trim(),
          remember: $('#remember').checked
        })
      });
      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        refreshCaptcha();
        if (response.status === 429 && data.retryAfterSeconds) {
          showAlert(data.error || 'Too many failed attempts.');
          failureCount += 1;
          if (failureCount >= config.forgotAfter) forgotWrap.hidden = false;
          startLockout(data.retryAfterSeconds);
          return;
        }
        failureCount += 1;
        showAlert(data.error || 'Invalid username or password.');
        if (failureCount >= config.forgotAfter) forgotWrap.hidden = false;
        if (data.errors) Object.entries(data.errors).forEach(([k, v]) => setError(k, v));
        return;
      }

      if (data.verifyRequired) {
        location.href = `/verify.html?email=${encodeURIComponent(data.email || '')}`;
        return;
      }
      if (data.otpRequired) {
        loginForm.hidden = true;
        $('#registerSwitch').hidden = true;
        forgotWrap.hidden = true;
        otpForm.hidden = false;
        const devNote = data.devMail ? ' Development mode: the code is written to logs/mail_outbox.log.' : '';
        $('#otpHint').textContent = `Enter the 6-digit code sent to ${data.email || 'your email'}. It expires in ${data.expiresIn ? Math.round(data.expiresIn / 60) : config.otpExpiryMinutes} minutes.${devNote}`;
        showAlert(data.message || 'Enter the code we emailed you.', 'info');
        startResendCooldown(60);
        $('#otpCode').focus();
        return;
      }
      location.href = '/dashboard.html';
    } catch (_) {
      showAlert('Unable to reach the authentication service.');
    } finally {
      if (lockUntil > Date.now()) {
        submitBtn.disabled = true;
      } else {
        submitBtn.disabled = false;
      }
      $('#submitText').hidden = false;
      $('#submitSpinner').hidden = true;
    }
  });

  otpForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    hideAlert();
    setError('otp', '');
    const code = $('#otpCode').value.replace(/\s/g, '');
    if (!/^\d{6}$/.test(code)) return setError('otp', 'Enter the 6-digit code.');
    const button = $('#otpSubmit');
    button.disabled = true;
    $('#otpSubmitText').hidden = true;
    $('#otpSpinner').hidden = false;
    try {
      const response = await secureFetch('/api/login/otp', {
        method: 'POST',
        body: JSON.stringify({ code })
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        setError('otp', data.error || 'That code could not be verified.');
        if (/request a new one/i.test(data.error || '')) $('#resend').disabled = false;
        return;
      }
      location.href = '/dashboard.html';
    } catch (_) {
      setError('otp', 'Unable to reach the authentication service.');
    } finally {
      button.disabled = false;
      $('#otpSubmitText').hidden = false;
      $('#otpSpinner').hidden = true;
    }
  });

  $('#resend').addEventListener('click', async () => {
    hideAlert();
    try {
      const response = await secureFetch('/api/login/resend', { method: 'POST', body: '{}' });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        showAlert(data.error || 'Could not resend the code.');
        if (data.retryAfterSeconds) startResendCooldown(data.retryAfterSeconds);
        return;
      }
      showAlert(data.message || 'A new code was sent.', 'success');
      if (data.devMail) showAlert(`${data.message || 'A new code was sent.'} Check logs/mail_outbox.log for the new code.`, 'success');
      startResendCooldown(60);
    } catch (_) {
      showAlert('Could not resend the code.');
    }
  });

  $('#otpBack').addEventListener('click', () => location.reload());
  $('#otpCode').addEventListener('input', (event) => {
    event.target.value = event.target.value.replace(/\D/g, '').slice(0, 6);
  });

  const params = new URLSearchParams(location.search);
  if (params.get('registered')) showAlert('Account verified. Sign in to continue.', 'success');

  loadConfig();
  refreshCaptcha();
})();
