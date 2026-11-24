// ==========================================
// 2. UTILITY FUNCTIONS
// ==========================================
const $ = s => document.querySelector(s);

const esc = s => String(s ?? '').replace(/[&<>'"]/g, c => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
}[c]));

const fmt = d => d ? new Date(d).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' }) : '—';
const initials = n => (n || 'U').split(' ').map(x => x[0]).slice(0, 2).join('').toUpperCase();
const humanizeStatus = s => (s || '').replaceAll('_', ' ').replace(/\b\w/g, x => x.toUpperCase());

// One source of truth for the backend status enum. Display labels may be
// humanized, but the keys must stay 1:1 with app/config.py.
const STATUS_META = {
  submitted:        { label: 'Submitted',        tone: 'blue' },
  under_review:     { label: 'Under Review',     tone: 'blue' },
  assigned:         { label: 'Assigned',         tone: 'blue' },
  accepted:         { label: 'Accepted',         tone: 'blue' },
  in_progress:      { label: 'In Progress',      tone: 'blue' },
  waiting:          { label: 'Waiting',          tone: 'amber' },
  handover:         { label: 'Handover',         tone: 'purple' },
  for_verification: { label: 'For Verification', tone: 'amber' },
  verified:         { label: 'Verified',         tone: 'green' },
  completed:        { label: 'Completed',        tone: 'green' },
  rejected:         { label: 'Rejected',         tone: 'red' },
  cancelled:        { label: 'Cancelled',        tone: 'gray' },
  overdue:          { label: 'Overdue',          tone: 'red' }
};

const statusMeta = s => STATUS_META[s] || { label: humanizeStatus(s), tone: 'gray' };
const statusLabel = s => statusMeta(s).label;

const badge = s => {
  const meta = statusMeta(s);
  return `<span class="badge badge-${meta.tone}">${esc(meta.label)}</span>`;
};

const hoursLabel = h => (h % 24 === 0) ? `${h / 24} day${h / 24 === 1 ? '' : 's'}` : `${h} hour${h === 1 ? '' : 's'}`;
const slaChip = st => ({
  due_soon: '<span class="badge badge-amber">Due soon</span>',
  overdue: '<span class="badge badge-red">Overdue</span>',
  escalated: '<span class="badge badge-red">Escalated</span>'
}[st] || '');

function empty(text, action = '') {
  return `<div class="empty">
    <span class="empty-icon" aria-hidden="true">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
        <path d="M3 7l9-4 9 4-9 4-9-4z"></path>
        <path d="M3 7v10l9 4 9-4V7"></path>
        <path d="M12 11v10"></path>
      </svg>
    </span>
    <p>${esc(text)}</p>
    ${action ? `<div class="empty-action">${action}</div>` : ''}
  </div>`;
}

function toast(msg) {
  const t = $('#toast');
  if (!t) return;
  t.textContent = msg;
  t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), 2800);
}

function enhanceTables(root = document) {
  root.querySelectorAll('table th:not([scope])').forEach(th => th.setAttribute('scope', 'col'));
}

function animateStatCounters(root) {
  if (!root) return;
  if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  root.querySelectorAll('.stat .num').forEach((el) => {
    const raw = (el.textContent || '').trim();
    if (!/^\d+$/.test(raw)) return;
    const target = Number(raw);
    if (!Number.isFinite(target) || target > 100000) return;
    const duration = 650;
    const started = performance.now();
    el.textContent = '0';
    const step = (now) => {
      const progress = Math.min(1, (now - started) / duration);
      const eased = 1 - Math.pow(1 - progress, 3);
      el.textContent = String(Math.round(target * eased));
      if (progress < 1) requestAnimationFrame(step);
      else el.textContent = raw;
    };
    requestAnimationFrame(step);
  });
}
