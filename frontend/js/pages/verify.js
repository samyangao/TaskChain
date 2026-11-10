// Registration OTP step. The server will not create a session until it passes.
(() => {
  const $ = (s) => document.querySelector(s);
  let timer = null;

  function showAlert(message, type = 'error') {
    $('#alertText').textContent = message;
    $('#alert').className = `alert show ${type}`;
  }
  function cooldown(seconds = 60) {
    clearInterval(timer);
    const button = $('#resend');
    let left = Math.max(1, Number(seconds) || 0);
    button.disabled = true;
    const tick = () => {
      button.textContent = left > 0 ? `Resend code in ${left}s` : 'Resend code';
      if (left <= 0) { clearInterval(timer); button.disabled = false; return; }
      left -= 1;
    };
    tick();
    timer = setInterval(tick, 1000);
  }

  const params = new URLSearchParams(location.search);
  const email = params.get('email');
  if (email) $('#emailText').textContent = email;
  if (params.get('dev') === '1') {
    const hint = document.createElement('p');
    hint.className = 'hint';
    hint.textContent = 'Development mode: the code is written to logs/mail_outbox.log.';
    document.querySelector('.card-head').appendChild(hint);
  }

  $('#code').addEventListener('input', (event) => {
    event.target.value = event.target.value.replace(/\D/g, '').slice(0, 6);
  });

  $('#verifyForm').addEventListener('submit', async (event) => {
    event.preventDefault();
    $('#error-code').textContent = '';
    const code = $('#code').value.replace(/\s/g, '');
    if (!/^\d{6}$/.test(code)) { $('#error-code').textContent = 'Enter the 6-digit code.'; return; }
    const button = $('#submit');
    button.disabled = true;
    $('#submitText').hidden = true;
    $('#submitSpinner').hidden = false;
    try {
      const response = await secureFetch('/api/register/verify', {
        method: 'POST',
        body: JSON.stringify({ code })
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        $('#error-code').textContent = data.error || 'Verification failed.';
        if (/request a new one/i.test(data.error || '')) $('#resend').disabled = false;
        return;
      }
      location.href = '/login.html?registered=1';
    } catch (_) {
      $('#error-code').textContent = 'Could not reach the server.';
    } finally {
      button.disabled = false;
      $('#submitText').hidden = false;
      $('#submitSpinner').hidden = true;
    }
  });

  $('#resend').addEventListener('click', async () => {
    try {
      const response = await secureFetch('/api/register/resend', { method: 'POST', body: '{}' });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        showAlert(data.error || 'Could not resend the code.');
        if (data.retryAfterSeconds) cooldown(data.retryAfterSeconds);
        return;
      }
      showAlert(data.message || 'A new code was sent.', 'success');
      cooldown(60);
    } catch (_) {
      showAlert('Could not resend the code.');
    }
  });

  cooldown(60);
  $('#code').focus();
})();
