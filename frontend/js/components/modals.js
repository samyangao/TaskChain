// ==========================================
// 6. MODALS & POPUPS
// ==========================================
function closeOnBackdrop(modal) {
  modal.addEventListener('click', e => { if (e.target === modal) modal.remove(); });
  modal.querySelector('.modal-close').onclick = () => modal.remove();
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
