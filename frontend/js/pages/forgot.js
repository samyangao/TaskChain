// Forgot Password: identify + CAPTCHA, security answer, reset OTP, reset link.
(() => {
  const $ = (s) => document.querySelector(s);
  let timer = null;

  function showAlert(message, type = 'error') {
    $('#alertText').textContent = message;
    $('#alert').className = `alert show ${type}`;
  }
  function refreshCaptcha() {
    $('#captchaImage').src = `/api/captcha?t=${Date.now()}`;
    $('#captcha').value = '';
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
  function step(title, copy) {
    $('#stepTitle').textContent = title;
    $('#stepCopy').textContent = copy;
  }

  function fillQuestions(questions) {
    const select = $('#questionNo');
    if (!select || !questions || !questions.length) return;
    select.innerHTML = '';
    questions.forEach((q) => {
      const option = document.createElement('option');
      option.value = q.number;
      option.textContent = `${q.number}. ${q.question}`;
      select.appendChild(option);
    });
  }

  async function loadQuestions() {
    try {
      const response = await fetch('/api/security/config', { credentials: 'same-origin' });
      if (!response.ok) return;
      const data = await response.json();
      fillQuestions(data.questions);
    } catch (_) { /* ignore */ }
  }

  $('#captchaRefresh').addEventListener('click', refreshCaptcha);

  $('#identifyForm').addEventListener('submit', async (event) => {
    event.preventDefault();
    $('#error-identifier').textContent = '';
    $('#error-captcha').textContent = '';
    const identifier = $('#identifier').value.trim();
    if (!identifier) { $('#error-identifier').textContent = 'Enter your username or email.'; return; }
    if (!$('#captcha').value.trim()) { $('#error-captcha').textContent = 'Type the CAPTCHA characters.'; return; }

    const button = $('#identifySubmit');
    button.disabled = true;
    $('#identifyText').hidden = true;
    $('#identifySpinner').hidden = false;
    try {
      const response = await secureFetch('/api/forgot/identify', {
        method: 'POST',
        body: JSON.stringify({ identifier, captcha: $('#captcha').value.trim() })
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        refreshCaptcha();
        showAlert(data.error || 'Could not continue.');
        return;
      }
      $('#identifyForm').hidden = true;
      $('#answerForm').hidden = false;
      fillQuestions(data.questions);
      step('Answer a question', 'Choose one of your three registered questions and enter the same answer twice.');
      showAlert(data.message || 'Choose a question.', 'info');
    } catch (_) {
      refreshCaptcha();
      showAlert('Could not reach the server.');
    } finally {
      button.disabled = false;
      $('#identifyText').hidden = false;
      $('#identifySpinner').hidden = true;
    }
  });

  $('#answerForm').addEventListener('submit', async (event) => {
    event.preventDefault();
    ['questionNo', 'answer', 'confirmAnswer'].forEach((key) => { $(`#error-${key}`).textContent = ''; });
    const answer = $('#answer').value.trim();
    const confirmAnswer = $('#confirmAnswer').value.trim();
    if (!answer) { $('#error-answer').textContent = 'Enter your answer.'; return; }
    if (answer.toLowerCase() !== confirmAnswer.toLowerCase()) { $('#error-confirmAnswer').textContent = 'Answers do not match.'; return; }

    const button = $('#answerSubmit');
    button.disabled = true;
    $('#answerText').hidden = true;
    $('#answerSpinner').hidden = false;
    try {
      const response = await secureFetch('/api/forgot/answer', {
        method: 'POST',
        body: JSON.stringify({ questionNo: Number($('#questionNo').value), answer, confirmAnswer })
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        showAlert(data.error || 'That answer is not correct.');
        return;
      }
      $('#answerForm').hidden = true;
      $('#otpForm').hidden = false;
      step('Verify the code', 'Enter the 6-digit reset code we emailed you.');
      showAlert(data.message || 'Enter the emailed code.', 'info');
      if (data.devMail) {
        const hint = document.createElement('p');
        hint.className = 'hint';
        hint.textContent = 'Development mode: the code is written to logs/mail_outbox.log.';
        document.querySelector('.card-head').appendChild(hint);
      }
      cooldown(60);
      $('#code').focus();
    } catch (_) {
      showAlert('Could not reach the server.');
    } finally {
      button.disabled = false;
      $('#answerText').hidden = false;
      $('#answerSpinner').hidden = true;
    }
  });

  $('#otpForm').addEventListener('submit', async (event) => {
    event.preventDefault();
    $('#error-code').textContent = '';
    const code = $('#code').value.replace(/\s/g, '');
    if (!/^\d{6}$/.test(code)) { $('#error-code').textContent = 'Enter the 6-digit code.'; return; }
    const button = $('#otpSubmit');
    button.disabled = true;
    $('#otpText').hidden = true;
    $('#otpSpinner').hidden = false;
    try {
      const response = await secureFetch('/api/forgot/otp', { method: 'POST', body: JSON.stringify({ code }) });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        $('#error-code').textContent = data.error || 'That code could not be verified.';
        if (/request a new one/i.test(data.error || '')) $('#resend').disabled = false;
        return;
      }
      location.href = data.resetUrl;
    } catch (_) {
      $('#error-code').textContent = 'Could not reach the server.';
    } finally {
      button.disabled = false;
      $('#otpText').hidden = false;
      $('#otpSpinner').hidden = true;
    }
  });

  $('#resend').addEventListener('click', async () => {
    try {
      const response = await secureFetch('/api/forgot/resend', { method: 'POST', body: '{}' });
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

  $('#code').addEventListener('input', (event) => {
    event.target.value = event.target.value.replace(/\D/g, '').slice(0, 6);
  });

  loadQuestions();
  refreshCaptcha();
})();
