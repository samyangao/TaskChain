// --- Component Helpers ---
function statusBars(s) {
  const vals = [['Submitted', s.new_requests], ['In Progress', s.in_progress], ['Waiting', s.waiting], ['Handover', s.handover], ['Verification', s.verification], ['Completed', s.completed]];
  const max = Math.max(1, ...vals.map(x => x[1]));
  return `<div class="bar-list">${vals.map(x => `
    <div class="bar-row">
      <span>${x[0]}</span>
      <div class="bar"><i style="width:${Math.round(x[1] / max * 100)}%"></i></div><b>${x[1]}</b>
    </div>`).join('')}</div>`;
}

function taskTable(rows) {
  return `<div class="table-wrap"><table class="table task-table">
    <thead><tr><th>Task</th><th>Requester</th><th>Responsible</th><th>Status</th><th>Priority</th><th>Due</th></tr></thead>
    <tbody>${rows.map(t => `
      <tr class="clickable" data-task="${t.id}">
        <td><strong>${esc(t.task_code)}</strong>${t.is_blocked ? ' <span class="badge badge-red">Blocked</span>' : ''}<br><span class="muted">${esc(t.title)}</span>${t.subtask_total ? `<span class="small muted"> · ${t.subtask_done}/${t.subtask_total} checklist</span>` : ''}</td>
        <td>${esc(t.requester || '—')}</td>
        <td>${esc(t.assignee || 'Unassigned')}</td>
        <td>${badge(t.status)}</td>
        <td class="priority-${esc(t.priority)}">${esc(t.priority)}</td>
        <td>${fmt(t.due_at)}${t.sla_state && slaChip(t.sla_state) ? `<br>${slaChip(t.sla_state)}` : ''}</td>
      </tr>`).join('')}
    </tbody></table></div>`;
}
