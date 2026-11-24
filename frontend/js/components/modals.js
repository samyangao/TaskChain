// ==========================================
// 6. MODALS & POPUPS
// ==========================================
let modalSeq = 0;

function closeOnBackdrop(modal) {
  const dialog = modal.querySelector('.modal');
  const closeBtn = modal.querySelector('.modal-close');
  const previousFocus = document.activeElement;

  if (dialog) {
    dialog.setAttribute('role', 'dialog');
    dialog.setAttribute('aria-modal', 'true');
    dialog.setAttribute('tabindex', '-1');
    const heading = dialog.querySelector('h2');
    if (heading) {
      if (!heading.id) heading.id = `modalTitle${++modalSeq}`;
      dialog.setAttribute('aria-labelledby', heading.id);
    } else if (!dialog.hasAttribute('aria-label')) {
      dialog.setAttribute('aria-label', 'Dialog');
    }
  }

  if (closeBtn) {
    if (!closeBtn.hasAttribute('aria-label')) closeBtn.setAttribute('aria-label', 'Close dialog');
    closeBtn.onclick = () => modal.remove();
  }

  const focusables = () => dialog
    ? [...dialog.querySelectorAll('a[href],button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])')]
        .filter(el => el.offsetParent !== null)
    : [];

  modal.addEventListener('click', e => { if (e.target === modal) modal.remove(); });
  modal.addEventListener('keydown', e => {
    if (e.key === 'Escape') {
      e.preventDefault();
      modal.remove();
      return;
    }
    if (e.key !== 'Tab') return;
    const items = focusables();
    if (!items.length) {
      e.preventDefault();
      (dialog || modal).focus();
      return;
    }
    const first = items[0];
    const last = items[items.length - 1];
    if (!dialog.contains(document.activeElement)) {
      e.preventDefault();
      first.focus();
    } else if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  });

  const observer = new MutationObserver(() => {
    if (document.body.contains(modal)) return;
    observer.disconnect();
    if (previousFocus && typeof previousFocus.focus === 'function') previousFocus.focus();
  });
  observer.observe(document.body, { childList: true });

  if (typeof enhanceTables === 'function') enhanceTables(modal);
  setTimeout(() => {
    if (document.body.contains(modal)) (dialog || modal).focus({ preventScroll: true });
  }, 0);
}

function accountModal() {
  const u = state.user;
  const m = document.createElement('div');
  m.className = 'modal-backdrop show';
  m.innerHTML = `
    <div class="modal" style="max-width:440px">
      <div class="modal-head">
        <div><div class="eyebrow">Account</div><h2>${esc(u.full_name)}</h2></div>
        <button class="modal-close">×</button>
      </div>
      <div class="grid" style="gap:10px">
        <div class="notice"><span class="small muted">Email</span><br><strong>${esc(u.email || '-')}</strong></div>
        <div class="notice"><span class="small muted">Role</span><br><strong style="text-transform:capitalize">${esc(u.role)}</strong></div>
        <button class="btn full" id="acctSecurity">Password, 2FA &amp; sessions</button>
      </div>
    </div>`;
  document.body.appendChild(m);
  closeOnBackdrop(m);
  m.querySelector('#acctSecurity').onclick = () => { m.remove(); state.page = 'security'; render(); };
}
