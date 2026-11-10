// Change Password page. The URL token is single-use and validated server-side.
(() => {
  const $ = (s) => document.querySelector(s);
  const token = new URLSearchParams(location.search).get('token') || '';
  let minPassword = 11;

  function showAlert(message, type = 'error') {
    $('#alertText').textContent = message;
    $('#alert').className = `alert show ${type}`;
  }
  function strength(password) {
    const classes = [/[a-z]/, /[A-Z]/, /\d/, /[^A-Za-z0-9]/].filter((r) => r.test(password)).length;
    if (password.length < minPassword || classes <= 1) return 'Weak';
    return classes === 2 ? 'Medium' : 'Strong';
  }
  function updateStrength() {
    const level = strength($('#password').value);
    $('#strengthBar').className = level.toLowerCase();
    $('#strengthBar').style.width = level === 'Weak' ? '33%' : level === 'Medium' ? '66%' : '100%';
    $('#strengthText').textContent = level;
  }

  async function loadConfig() {
    try {
      const response = await fetch('/api/security/config', { credentials: 'same-origin' });
      if (response.ok) {
        const data = await response.json();
        minPassword = data.minPassword || minPassword;
      }
    } catch (_) { /* seeded default */ }
  }

  async function validateToken() {
    if (!token) {
      $('#tokenState').textContent = 'This password reset link is invalid or has already been used.';
      showAlert('This password reset link is invalid or has already been used.');
      return;
    }
    try {
      const response = await fetch(`/api/reset/validate?token=${encodeURIComponent(token)}`, { credentials: 'same-origin' });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        $('#tokenState').textContent = data.error || 'This reset link is invalid or has expired.';
        showAlert(data.error || 'This reset link is invalid or has expired.');
        return;
      }
      $('#tokenState').textContent = `Reset link verified for ${data.username}.`;
      $('#resetForm').hidden = false;
      $('#password').focus();
    } catch (_) {
      $('#tokenState').textContent = 'Could not verify the reset link.';
      showAlert('Could not verify the reset link.');
    }
  }

  $('#password').addEventListener('input', updateStrength);
  $('#showPassword').addEventListener('click', () => {
    const input = $('#password');
    const reveal = input.type === 'password';
    input.type = reveal ? 'text' : 'password';
    $('#confirmPassword').type = input.type;
    $('#showPassword').textContent = reveal ? 'Hide' : 'Show';
    $('#showPassword').setAttribute('aria-pressed', String(reveal));
  });

  $('#resetForm').addEventListener('submit', async (event) => {
    event.preventDefault();
    $('#error-password').textContent = '';
    $('#error-confirmPassword').textContent = '';
    const password = $('#password').value;
    const confirmPassword = $('#confirmPassword').value;
    if (password !== confirmPassword) {
      $('#error-confirmPassword').textContent = 'Mismatch Password.';
      showAlert('Mismatch Password.');
      return;
    }
    if (!password) { $('#error-password').textContent = 'Password is required.'; return; }
    if (password.length < minPassword) { $('#error-password').textContent = `Password must be at least ${minPassword} characters.`; return; }
    if (strength(password) === 'Weak') { $('#error-password').textContent = 'Password is too weak.'; return; }

    const button = $('#submit');
    button.disabled = true;
    $('#submitText').hidden = true;
    $('#submitSpinner').hidden = false;
    try {
      const response = await secureFetch('/api/reset-password', {
        method: 'POST',
        body: JSON.stringify({ token, password, confirmPassword })
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        showAlert(data.error || 'Could not change the password.');
        $('#error-password').textContent = data.error || '';
        return;
      }
      $('#resetForm').hidden = true;
      $('#tokenState').textContent = data.message || 'Successfully Change Password.';
      showAlert(`${data.message || 'Successfully Change Password.'} You can now sign in.`, 'success');
      setTimeout(() => { location.href = '/login.html'; }, 2200);
    } catch (_) {
      showAlert('Could not reach the server.');
    } finally {
      button.disabled = false;
      $('#submitText').hidden = false;
      $('#submitSpinner').hidden = true;
    }
  });

  loadConfig();
  updateStrength();
  validateToken();
})();
