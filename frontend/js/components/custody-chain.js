// --- Chain of custody (Phase 1) ---
function chainStatusCard(r) {
  const ok = !!r.valid;
  const broken = r.broken_sequence ?? r.broken_record;
  return `<div class="chain-status ${ok ? 'is-valid' : 'is-invalid'}" role="status">
    <div class="chain-status-label">CHAIN STATUS</div>
    <div class="chain-status-verdict">${ok ? '✓ VALID' : '✕ INVALID'}</div>
    ${ok
      ? `<div>${r.record_count ? `${r.record_count} record${r.record_count === 1 ? '' : 's'} verified` : 'No custody records yet'}</div>`
      : `<div>Broken record: #${esc(broken)}</div>
         <div class="small">${esc(r.reason)}</div>
         <div class="small">Expected hash: <code class="hash">${esc(r.expected_hash || r.expected_previous_hash || '—')}</code></div>
         <div class="small">Stored hash: <code class="hash">${esc(r.stored_hash || r.stored_previous_hash || '—')}</code></div>`}
    <div class="small muted">Last verified: ${fmt(r.last_verified)}</div>
  </div>`;
}

async function chainReportModal(id) {
  const d = await api('/api/tasks/' + id + '/chain/report');
  const r = d.report, t = r.task;
  const modal = document.createElement('div');
  modal.className = 'modal-backdrop show print-target';

  const handoversHtml = r.handovers.length ? r.handovers.map(handoverDetailHtml).join('') : '<div class="empty">No handovers recorded.</div>';

  const eventsHtml = r.chain.length ? r.chain.map(ev => `
    <div class="report-event">
      <div class="report-event-head">
        <strong>#${ev.sequence_number} · ${esc(statusLabel(ev.event_type))}</strong>
        <span class="small muted">${fmt(ev.event_timestamp)}</span>
      </div>
      <div class="report-actor small">Actor: ${esc(ev.actor_name)} (${esc(ev.actor_email)})</div>
      <div class="report-data">${renderKv(ev.event_data)}</div>
      <div class="report-hash"><span class="small muted">Previous hash</span><code class="hash">${esc(ev.previous_hash)}</code></div>
      <div class="report-hash"><span class="small muted">Current hash</span><code class="hash">${esc(ev.current_hash)}</code></div>
    </div>`).join('') : '<div class="empty">No custody events recorded.</div>';

  modal.innerHTML = `
    <div class="modal chain-report-modal" style="max-width:820px">
      <div class="modal-head">
        <div><div class="eyebrow">Chain of Custody Report</div><h2>${esc(t.task_code)} — ${esc(t.title)}</h2></div>
        <div class="no-print" style="display:flex;gap:8px;align-items:center">
          <button class="btn primary small" id="printReport">Print</button>
          <button class="modal-close" aria-label="Close">×</button>
        </div>
      </div>
      <div class="chain-report">
        <div class="report-grid">
          <div><span class="small muted">Requester</span><br><strong>${esc(r.requester)}</strong> <span class="small muted">${esc(r.requester_email)}</span></div>
          <div><span class="small muted">Current status</span><br><strong>${esc(statusLabel(r.current_status))}</strong></div>
          <div><span class="small muted">Category / priority</span><br><strong>${esc(t.category)} · ${esc(t.priority)}</strong></div>
          <div><span class="small muted">Due (SLA)</span><br><strong>${fmt(t.due_at)}</strong></div>
          <div><span class="small muted">Responsible</span><br><strong>${esc(t.assignee || 'Unassigned')}</strong></div>
          <div><span class="small muted">Generated</span><br><strong>${fmt(r.generated_at)}</strong> <span class="small muted">by ${esc(r.generated_by)}</span></div>
        </div>
        <h3>Verification result</h3>
        ${chainStatusCard(r.verification)}
        <h3>Handovers</h3>
        ${handoversHtml}
        <h3>Time in custody</h3>
        ${custodyHtml(r.custody)}
        <h3>Custody events (${r.chain.length})</h3>
        ${eventsHtml}
      </div>
    </div>`;

  document.body.appendChild(modal);
  closeOnBackdrop(modal);
  modal.querySelector('#printReport').onclick = () => window.print();
}

function renderKv(obj) {
  if (!obj) return '<span class="small muted">No data</span>';
  const entries = typeof obj === 'string' ? JSON.parse(obj) : obj;
  const val = v => (v !== null && typeof v === 'object') ? JSON.stringify(v) : String(v ?? '—');
  return Object.entries(entries).map(([k, v]) => `
    <span class="report-kv">
      <span class="small muted">${esc(k)}</span><br><strong>${esc(val(v))}</strong>
    </span>`).join('');
}
