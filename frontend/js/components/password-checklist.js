// Shared password requirement checklist and strength calculation.
// The server remains the authority; these rules mirror the seeded policy.

function passwordRuleState(password, minLength = 11) {
  const value = password || '';
  return {
    length: value.length >= minLength,
    upper: /[A-Z]/.test(value),
    lower: /[a-z]/.test(value),
    number: /\d/.test(value),
    special: /[^A-Za-z0-9]/.test(value)
  };
}

function passwordStrengthLevel(password, minLength = 11) {
  const rules = passwordRuleState(password, minLength);
  const classes = [rules.upper, rules.lower, rules.number, rules.special].filter(Boolean).length;
  if (!rules.length || classes <= 1) return 'Weak';
  return classes < 4 ? 'Medium' : 'Strong';
}

function updatePasswordChecklist(root, password, minLength = 11) {
  if (!root) return;
  const rules = passwordRuleState(password, minLength);
  root.querySelectorAll('[data-password-min]').forEach(el => {
    el.textContent = String(minLength);
  });
  root.querySelectorAll('[data-password-rule]').forEach(item => {
    const met = !!rules[item.dataset.passwordRule];
    item.classList.toggle('is-met', met);
    item.classList.toggle('is-missing', !met);
    const icon = item.querySelector('.pw-rule-icon');
    if (icon) icon.textContent = met ? '✓' : '✕';
    const text = item.querySelector('.pw-rule-text');
    if (text) item.setAttribute('aria-label', `${met ? 'Met' : 'Not met'}: ${text.textContent.trim()}`);
  });
}
