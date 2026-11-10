// ==========================================
// 2. UTILITY FUNCTIONS
// ==========================================
const $ = s => document.querySelector(s);

const esc = s => String(s ?? '').replace(/[&<>'"]/g, c => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
}[c]));

const fmt = d => d ? new Date(d).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' }) : '—';
const initials = n => (n || 'U').split(' ').map(x => x[0]).slice(0, 2).join('').toUpperCase();
const statusLabel = s => (s || '').replaceAll('_', ' ').replace(/\b\w/g, x => x.toUpperCase());

const badge = s => {
  let c = 'gray';
  if (['completed', 'verified'].includes(s)) c = 'green';
  else if (['in_progress', 'accepted', 'assigned', 'submitted'].includes(s)) c = 'blue';
  else if (['waiting', 'for_verification', 'overdue'].includes(s)) c = 'orange';
  else if (['rejected', 'cancelled'].includes(s)) c = 'red';
  else if (s === 'handover') c = 'purple';
  
  return `<span class="badge badge-${c}">${esc(statusLabel(s))}</span>`;
};

const hoursLabel = h => (h % 24 === 0) ? `${h / 24} day${h / 24 === 1 ? '' : 's'}` : `${h} hour${h === 1 ? '' : 's'}`;
const slaChip = st => ({
  due_soon: '<span class="badge badge-orange">Due soon</span>',
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
