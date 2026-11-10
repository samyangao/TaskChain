async function calendarPage(c) {
  setHeader('Calendar');
  const d = await api('/api/tasks');
  const dated = d.tasks.filter(t => t.due_at && !['completed', 'cancelled', 'verified'].includes(t.status))
    .sort((a, b) => new Date(a.due_at) - new Date(b.due_at));
  const byDay = {};
  dated.forEach(t => (byDay[new Date(t.due_at).toDateString()] ||= []).push(t));
  c.innerHTML = `<div class="card"><div class="card-title"><h3>Upcoming deadlines</h3></div>${
    dated.length ? `<div class="timeline">${Object.entries(byDay).map(([day, ts]) => `
      <div class="timeline-item"><div class="timeline-time">${esc(day)}</div><div class="timeline-body">${
        ts.map(t => `<p><strong data-task="${t.id}" style="cursor:pointer">${esc(t.task_code)} · ${esc(t.title)}</strong> ${badge(t.status)} ${slaChip(t.sla_state)}</p>`).join('')}</div></div>`).join('')}</div>`
    : empty('No deadlines scheduled.')}</div>`;
  c.querySelectorAll('[data-task]').forEach(x => x.onclick = () => openTask(x.dataset.task));
}
