// Registration: browser-side rules mirror the server; the server remains the authority.
(() => {
  const $ = (s) => document.querySelector(s);
  const config = { minUsername: 6, maxUsername: 19, minPassword: 11, maxName: 23, questions: [] };
  let usernameAvailable = null;
  let usernameTimer = null;

  const TRIPLE = /([A-Za-z])\1\1/i;
  const TITLE_WORD = /^[A-Z][a-z]*$/;
  const EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
  const USERNAME = /^[A-Za-z][A-Za-z0-9]*$/;

  const TOTAL_STEPS = 5;
  const STEP_NAMES = { 1: 'Identity', 2: 'Address', 3: 'Account', 4: 'Security', 5: 'Work & Consent' };
  const STEP_NEXT = {
    1: 'Continue to Address',
    2: 'Continue to Account',
    3: 'Continue to Security',
    4: 'Continue to Work & Consent'
  };
  const STEP_FIELDS = {
    1: ['idNumber', 'firstName', 'middleName', 'familyName', 'nameExtension', 'birthdate'],
    2: ['purokStreet', 'barangay', 'municipality', 'province', 'country', 'zipCode'],
    3: ['email', 'username', 'password', 'confirmPassword'],
    4: ['answer4', 'answer7', 'answer1'],
    5: ['officeUnit', 'contactNumber', 'dateOfAppointment', 'positionDesignation', 'privacyConsent', 'captcha']
  };
  let currentStep = 1;
  let maxStep = 1;

  const stepper = $('#stepper');
  const stepElements = [...document.querySelectorAll('[data-step]')];
  const stepButtons = [...document.querySelectorAll('[data-step-button]')];
  const stepperBar = $('#stepperBar');
  const stepperHint = $('#stepperHint');
  const stepBack = $('#stepBack');
  const stepNext = $('#stepNext');
  const submitButton = $('#submit');
  const reduceMotion = () => window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

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
  function setError(key, message) { const el = $(`#error-${key}`); if (el) el.textContent = message || ''; }
  function clearErrors() {
    document.querySelectorAll('.field-error').forEach((el) => { el.textContent = ''; });
  }

  function validateName(value, label, required = true) {
    const text = (value || '').trim();
    if (!text) return required ? `${label} is required.` : '';
    if (text.length < 2) return `${label} must be at least 2 characters.`;
    if (text.length > config.maxName) return `${label} must be at most ${config.maxName} characters.`;
    if (/\d/.test(text)) return `Numbers are not allowed in ${label}.`;
    if (/[^A-Za-z ]/.test(text)) return `Special characters are not allowed in ${label}.`;
    if (/ {2}/.test(text)) return 'Double space is not allowed.';
    const letters = text.split('').filter((ch) => /[A-Za-z]/.test(ch));
    if (letters.length && letters.every((ch) => ch === ch.toUpperCase())) return 'Do not use all capital letters.';
    if (TRIPLE.test(text)) return 'Three consecutive identical letters are not allowed.';
    if (!/^[A-Z]/.test(text)) return 'First letter of your name must be capital.';
    if (text.split(' ').some((word) => !TITLE_WORD.test(word))) return 'Only the first letter of each word should be capital.';
    return '';
  }

  function validateBirthdate(value) {
    if (!value) return 'Birthdate is required.';
    const born = new Date(`${value}T00:00:00`);
    if (Number.isNaN(born.getTime())) return 'Enter a valid birthdate.';
    const today = new Date();
    if (born > today) return 'Birthdate cannot be in the future.';
    let age = today.getFullYear() - born.getFullYear();
    const m = today.getMonth() - born.getMonth();
    if (m < 0 || (m === 0 && today.getDate() < born.getDate())) age -= 1;
    $('#age').value = age;
    if (age < 18) return 'You must be at least 18 years old to register.';
    return '';
  }

  function validateAddress() {
    const errors = {};
    const purok = $('#purokStreet').value.trim();
    if (!purok) errors.purokStreet = 'Purok / Street is required.';
    else if (purok.length < 3 || purok.length > 50) errors.purokStreet = 'Purok / Street must be 3-50 characters.';
    else if (!/^[A-Za-z0-9 ]+$/.test(purok)) errors.purokStreet = 'Purok / Street may contain letters, digits and spaces only.';
    else if (/ {2}/.test(purok)) errors.purokStreet = 'Double space is not allowed.';

    [['barangay', 'Barangay'], ['municipality', 'Municipality / City'], ['province', 'Province'], ['country', 'Country']]
      .forEach(([key, label]) => {
        const text = $(`#${key}`).value.trim();
        if (!text) errors[key] = `${label} is required.`;
        else if (text.length < 2 || text.length > 50) errors[key] = `${label} must be 2-50 characters.`;
        else if (!/^[A-Za-z ]+$/.test(text)) errors[key] = `${label} may contain letters and spaces only.`;
        else if (/ {2}/.test(text)) errors[key] = 'Double space is not allowed.';
        else if (text.split(' ').some((word) => !TITLE_WORD.test(word))) errors[key] = `${label} must be in Title Case.`;
      });

    if (!/^\d{4}$/.test($('#zipCode').value.trim())) errors.zipCode = 'ZIP Code must be exactly 4 digits.';
    return errors;
  }

  function validateAnswer(value) {
    const text = (value || '').trim();
    if (!text) return 'Each security answer is required.';
    if (text.length < 2 || text.length > 50) return 'Answer must be 2-50 characters.';
    if (!/^[A-Za-z ]+$/.test(text)) return 'Answer may contain letters and spaces only.';
    if (/ {2}/.test(text)) return 'Double space is not allowed.';
    return '';
  }

  function strength(password) {
    const classes = [/[a-z]/, /[A-Z]/, /\d/, /[^A-Za-z0-9]/].filter((r) => r.test(password)).length;
    if (password.length < config.minPassword || classes <= 1) return 'Weak';
    return classes === 2 ? 'Medium' : 'Strong';
  }

  function validateUsername(value) {
    const text = (value || '').trim();
    if (!text) return 'Username is required.';
    if (!USERNAME.test(text)) return 'Username must start with a letter and contain only letters and digits.';
    if (text.length < config.minUsername) return `Username must be at least ${config.minUsername} characters.`;
    if (text.length > config.maxUsername) return `Username must be at most ${config.maxUsername} characters.`;
    return '';
  }

  function validatePassword() {
    const value = $('#password').value;
    if (!value) return 'Password is required.';
    if (value.length < config.minPassword) return `Password must be at least ${config.minPassword} characters.`;
    if (value.length > 64) return 'Password must be at most 64 characters.';
    if (strength(value) === 'Weak') return 'Password is too weak. Use uppercase, lowercase, numbers or symbols.';
    if (value !== $('#confirmPassword').value) return 'Passwords do not match.';
    return '';
  }

  function validateSystem() {
    const errors = {};
    if (!$('#officeUnit').value) errors.officeUnit = 'Please select a valid Office/Unit.';
    if (!/^09\d{9}$/.test($('#contactNumber').value.trim())) errors.contactNumber = 'Contact number must be 11 digits and start with 09.';
    const appointment = $('#dateOfAppointment').value;
    if (!appointment) errors.dateOfAppointment = 'Date of Appointment is required.';
    else if (new Date(`${appointment}T00:00:00`) > new Date()) errors.dateOfAppointment = 'Date of Appointment cannot be in the future.';
    const position = $('#positionDesignation').value.trim();
    if (!position) errors.positionDesignation = 'Position / Designation is required.';
    else if (position.length < 2 || position.length > 50) errors.positionDesignation = 'Position / Designation must be 2-50 characters.';
    else if (!/^[A-Za-z ]+$/.test(position)) errors.positionDesignation = 'Position / Designation may contain letters and spaces only.';
    else if (/ {2}/.test(position)) errors.positionDesignation = 'Double space is not allowed.';
    return errors;
  }

  function refreshCaptcha() {
    $('#captchaImage').src = `/api/captcha?t=${Date.now()}`;
    $('#captcha').value = '';
  }

  function collect() {
    let extension = $('#nameExtension').value;
    if (extension === 'Other') extension = $('#otherExtension').value.trim();
    return {
      idNumber: $('#idNumber').value.trim(),
      firstName: $('#firstName').value.trim(),
      middleName: $('#middleName').value.trim(),
      familyName: $('#familyName').value.trim(),
      nameExtension: extension,
      birthdate: $('#birthdate').value,
      purokStreet: $('#purokStreet').value.trim(),
      barangay: $('#barangay').value.trim(),
      municipality: $('#municipality').value.trim(),
      province: $('#province').value.trim(),
      country: $('#country').value.trim(),
      zipCode: $('#zipCode').value.trim(),
      email: $('#email').value.trim(),
      username: $('#username').value.trim(),
      password: $('#password').value,
      confirmPassword: $('#confirmPassword').value,
      answers: [
        { questionNo: 4, answer: $('#answer4').value.trim(), confirmAnswer: $('#confirmAnswer4').value.trim() },
        { questionNo: 7, answer: $('#answer7').value.trim(), confirmAnswer: $('#confirmAnswer7').value.trim() },
        { questionNo: 1, answer: $('#answer1').value.trim(), confirmAnswer: $('#confirmAnswer1').value.trim() }
      ],
      officeUnit: $('#officeUnit').value,
      contactNumber: $('#contactNumber').value.trim(),
      dateOfAppointment: $('#dateOfAppointment').value,
      positionDesignation: $('#positionDesignation').value.trim(),
      privacyConsent: $('#privacyConsent').checked,
      captcha: $('#captcha').value.trim(),
      website: $('#website').value
    };
  }

  function validateAll(data) {
    const errors = {};
    if (!/^\d{4}-\d{4}$/.test(data.idNumber)) errors.idNumber = 'ID Number must follow the format xxxx-xxxx.';
    const nameChecks = [
      ['firstName', 'First Name', true],
      ['middleName', 'Middle Name', false],
      ['familyName', 'Family Name', true]
    ];
    nameChecks.forEach(([key, label, required]) => {
      const message = validateName(data[key], label, required);
      if (message) errors[key] = message;
    });
    if (data.nameExtension && !['Jr.', 'Sr.', 'I', 'II', 'III', 'IV', 'IX', 'X'].includes(data.nameExtension)) {
      errors.nameExtension = 'Select a valid Name Extension.';
    }
    const birthMessage = validateBirthdate(data.birthdate);
    if (birthMessage) errors.birthdate = birthMessage;
    Object.assign(errors, validateAddress());

    if (!data.email) errors.email = 'Email is required.';
    else if (data.email.length > 100 || !EMAIL.test(data.email)) errors.email = 'Please enter a valid email address.';
    const usernameMessage = validateUsername(data.username);
    if (usernameMessage) errors.username = usernameMessage;
    else if (usernameAvailable === false) errors.username = 'This username is already taken.';
    const passwordMessage = validatePassword();
    if (passwordMessage) errors.password = passwordMessage;

    data.answers.forEach((item) => {
      const message = validateAnswer(item.answer);
      if (message) errors[`answer${item.questionNo}`] = message;
      else if (item.answer.toLowerCase() !== item.confirmAnswer.toLowerCase()) errors[`answer${item.questionNo}`] = 'Answers do not match.';
    });

    Object.assign(errors, validateSystem());
    if (!data.privacyConsent) errors.privacyConsent = 'You must agree to the Privacy Notice to register.';
    if (!data.captcha) errors.captcha = 'Type the CAPTCHA characters.';
    return errors;
  }

  function errorStep(errors) {
    let earliest = TOTAL_STEPS;
    Object.keys(errors).forEach((key) => {
      for (let step = 1; step <= TOTAL_STEPS; step += 1) {
        if (STEP_FIELDS[step].includes(key) && step < earliest) earliest = step;
      }
    });
    return earliest;
  }

  function validateStep(step, data) {
    const all = validateAll(data);
    const allowed = new Set(STEP_FIELDS[step] || []);
    const errors = {};
    Object.entries(all).forEach(([key, message]) => {
      if (allowed.has(key)) errors[key] = message;
    });
    return errors;
  }

  function goToStep(step, { force = false, focus = true, scroll = true } = {}) {
    const target = Math.min(TOTAL_STEPS, Math.max(1, Number(step) || 1));
    if (!force && target > maxStep) return;
    currentStep = target;

    stepElements.forEach((element) => {
      element.hidden = Number(element.dataset.step) !== currentStep;
    });
    stepButtons.forEach((button) => {
      const number = Number(button.dataset.stepButton);
      button.classList.toggle('active', number === currentStep);
      button.classList.toggle('done', number < currentStep);
      button.disabled = number > maxStep;
      if (number === currentStep) button.setAttribute('aria-current', 'step');
      else button.removeAttribute('aria-current');
    });

    stepperBar.style.width = `${((currentStep - 1) / (TOTAL_STEPS - 1)) * 100}%`;
    stepperHint.textContent = `Step ${currentStep} of ${TOTAL_STEPS} · ${STEP_NAMES[currentStep]}`;
    stepBack.hidden = currentStep === 1;
    stepNext.hidden = currentStep === TOTAL_STEPS;
    submitButton.hidden = currentStep !== TOTAL_STEPS;
    stepNext.textContent = STEP_NEXT[currentStep] || 'Continue';
    if (currentStep === TOTAL_STEPS && scroll) refreshCaptcha();

    const panel = stepElements.find((element) => !element.hidden);
    if (panel && scroll) {
      panel.classList.remove('step-enter');
      void panel.offsetWidth;
      panel.classList.add('step-enter');
    }
    if (scroll && stepper) {
      stepper.scrollIntoView({ behavior: reduceMotion() ? 'auto' : 'smooth', block: 'start' });
    }
    if (focus) {
      const first = panel?.querySelector('input:not([type="hidden"]):not([readonly]), select, textarea');
      if (first) first.focus({ preventScroll: true });
    }
  }

  function showErrors(errors) {
    Object.entries(errors).forEach(([key, message]) => setError(key, message));
    const first = document.querySelector('[data-step]:not([hidden]) .field-error:not(:empty)');
    if (first) first.scrollIntoView({ behavior: reduceMotion() ? 'auto' : 'smooth', block: 'center' });
  }

  // Live password meter
  function updateStrength() {
    const value = $('#password').value;
    const level = strength(value);
    const bar = $('#strengthBar');
    bar.className = level.toLowerCase();
    bar.style.width = level === 'Weak' ? '33%' : level === 'Medium' ? '66%' : '100%';
    $('#strengthText').textContent = level;
  }

  // Live username availability
  function checkUsername() {
    const username = $('#username').value.trim();
    const hint = $('#usernameHint');
    usernameAvailable = null;
    const local = validateUsername(username);
    if (local) { hint.textContent = local; hint.className = 'hint error'; return; }
    hint.textContent = 'Checking…'; hint.className = 'hint';
    clearTimeout(usernameTimer);
    usernameTimer = setTimeout(async () => {
      try {
        const response = await fetch(`/api/username-available?username=${encodeURIComponent(username)}`, { credentials: 'same-origin' });
        const data = await response.json();
        if ($('#username').value.trim() !== username) return;
        usernameAvailable = !!data.available;
        hint.textContent = data.message || '';
        hint.className = `hint ${data.available ? 'ok' : 'error'}`;
      } catch (_) {
        hint.textContent = '';
      }
    }, 400);
  }

  async function loadConfig() {
    try {
      const response = await fetch('/api/security/config', { credentials: 'same-origin' });
      if (response.ok) Object.assign(config, await response.json());
      (config.questions || []).forEach((q) => {
        const label = $(`#label-q${q.number}`);
        if (label) label.textContent = `${q.number}. ${q.question} *`;
      });
      $('#username').placeholder = `${config.minUsername}–${config.maxUsername} letters and digits, starts with a letter`;
    } catch (_) { /* defaults are seeded */ }
  }

  $('#birthdate').addEventListener('change', () => {
    const message = validateBirthdate($('#birthdate').value);
    setError('birthdate', message);
  });
  $('#password').addEventListener('input', updateStrength);
  $('#username').addEventListener('input', checkUsername);
  $('#nameExtension').addEventListener('change', () => {
    const other = $('#nameExtension').value === 'Other';
    $('#otherExtensionWrap').hidden = !other;
    if (other) $('#otherExtension').focus();
  });
  $('#showPassword').addEventListener('click', () => {
    const input = $('#password');
    const reveal = input.type === 'password';
    input.type = reveal ? 'text' : 'password';
    $('#confirmPassword').type = input.type;
    $('#showPassword').textContent = reveal ? 'Hide' : 'Show';
    $('#showPassword').setAttribute('aria-pressed', String(reveal));
  });
  $('#captchaRefresh').addEventListener('click', refreshCaptcha);
  $('#contactNumber').addEventListener('input', (event) => {
    event.target.value = event.target.value.replace(/\D/g, '').slice(0, 11);
  });
  $('#zipCode').addEventListener('input', (event) => {
    event.target.value = event.target.value.replace(/\D/g, '').slice(0, 4);
  });
  $('#idNumber').addEventListener('input', (event) => {
    let digits = event.target.value.replace(/\D/g, '').slice(0, 8);
    event.target.value = digits.length > 4 ? `${digits.slice(0, 4)}-${digits.slice(4)}` : digits;
  });

  stepNext.addEventListener('click', () => {
    hideAlert();
    clearErrors();
    const errors = validateStep(currentStep, collect());
    if (Object.keys(errors).length) {
      showErrors(errors);
      showAlert('Please correct the highlighted fields.');
      return;
    }
    maxStep = Math.max(maxStep, currentStep + 1);
    goToStep(currentStep + 1);
  });

  stepBack.addEventListener('click', () => {
    hideAlert();
    goToStep(currentStep - 1);
  });

  stepButtons.forEach((button) => {
    button.addEventListener('click', () => {
      const number = Number(button.dataset.stepButton);
      if (number <= maxStep) {
        hideAlert();
        goToStep(number);
      }
    });
  });

  $('#registerForm').addEventListener('keydown', (event) => {
    if (event.key !== 'Enter' || currentStep >= TOTAL_STEPS) return;
    if (event.target.matches('textarea, button') || event.target.type === 'checkbox') return;
    event.preventDefault();
    stepNext.click();
  });

  $('#registerForm').addEventListener('submit', async (event) => {
    event.preventDefault();
    hideAlert();
    clearErrors();
    const data = collect();
    const errors = validateAll(data);
    if (Object.keys(errors).length) {
      const targetStep = errorStep(errors);
      maxStep = Math.max(maxStep, targetStep);
      goToStep(targetStep, { force: true, focus: false, scroll: false });
      showErrors(errors);
      showAlert('Please correct the highlighted fields.');
      refreshCaptcha();
      return;
    }

    const button = submitButton;
    button.disabled = true;
    $('#submitText').hidden = true;
    $('#submitSpinner').hidden = false;
    try {
      const response = await secureFetch('/api/register', {
        method: 'POST',
        body: JSON.stringify(data)
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        refreshCaptcha();
        if (payload.errors) {
          clearErrors();
          const targetStep = errorStep(payload.errors);
          maxStep = Math.max(maxStep, targetStep);
          goToStep(targetStep, { force: true, focus: false, scroll: false });
          showErrors(payload.errors);
        }
        showAlert(payload.error || 'Registration failed.');
        return;
      }
      location.href = `/verify.html?email=${encodeURIComponent(payload.email || data.email)}${payload.devMail ? '&dev=1' : ''}`;
    } catch (_) {
      refreshCaptcha();
      showAlert('Could not reach the server. Try again.');
    } finally {
      button.disabled = false;
      $('#submitText').hidden = false;
      $('#submitSpinner').hidden = true;
    }
  });

  goToStep(1, { focus: false, scroll: false });
  loadConfig();
  updateStrength();
})();
