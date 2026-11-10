// Admin-only read-only security monitor. No edit or delete controls exist.
let monitorTimer = null;

async function monitorPage(c) {
  setHeader('Security Monitor', 'Admin');
  secureFetch('/api/admin/security/viewed', { method: 'POST', body: '{}' }).catch(() => {});

  c.innerHTML = `
    <div class="card">
      <div class="card-title">
        <h3>Security monitoring</h3>
        <span class="muted small">Read-only · refreshes every 60 seconds</span>
      </div>
      <div class="monitor-filters">
        <label>From <input type="date" id="filterFrom"></label>
        <label>To <input type="date" id="filterTo"></label>
        <label>Event
          <select id="filterEvent"><option value="">All events</option></select>
        </label>
        <label>Username <input type="text" id="filterUser" placeholder="username typed"></label>
        <label>IP <input type="text" id="filterIp" placeholder="e.g. 127.0.0.1"></label>
        <div class="monitor-actions">
          <button class="btn primary" id="filterApply">Apply</button>
          <button class="btn" id="filterClear">Clear</button>
        </div>
      </div>
    </div>
    <div id="monitorBody">
      <div class="skeleton-grid">
        ${'<div class="skeleton-card"><div class="skeleton skeleton-line"></div><div class="skeleton skeleton-line"></div><div class="skeleton skeleton-line"></div></div>'.repeat(4)}
      </div>
      <div class="card monitor-gap">
        <div class="skeleton skeleton-title"></div>
        <div class="skeleton skeleton-line"></div>
        <div class="skeleton skeleton-line short"></div>
        <div class="skeleton skeleton-line tiny"></div>
      </div>
    </div>`;

  $('#filterApply').onclick = () => loadMonitorBody();
  $('#filterClear').onclick = () => {
    ['filterFrom', 'filterTo', 'filterUser', 'filterIp'].forEach((id) => { $(`#${id}`).value = ''; });
    $('#filterEvent').value = '';
    loadMonitorBody();
  };
  $('#filterEvent').onchange = () => loadMonitorBody();

  await loadMonitorBody();
  clearInterval(monitorTimer);
  monitorTimer = setInterval(() => {
    if (state.page !== 'monitor') { clearInterval(monitorTimer); return; }
    loadMonitorBody();
  }, 60000);
}

function monitorQuery() {
  const params = new URLSearchParams();
  const add = (key, id) => { const value = $(`#${id}`)?.value?.trim(); if (value) params.set(key, value); };
  add('from', 'filterFrom');
  add('to', 'filterTo');
  add('eventType', 'filterEvent');
  add('username', 'filterUser');
  add('ip', 'filterIp');
  return params.toString();
}

function barsSvg(hourly) {
  const max = Math.max(1, ...hourly.map((item) => item.count));
  const width = 18, gap = 2, height = 120;
  const bars = hourly.map((item, index) => {
    const barHeight = Math.max(2, Math.round((item.count / max) * (height - 12)));
    const x = index * (width + gap);
    const y = height - barHeight;
    return `<rect x="${x}" y="${y}" width="${width - 2}" height="${barHeight}" rx="2" fill="${item.count ? '#22c55e' : '#26332b'}">
      <title>${esc(item.hour)} — ${item.count} failed</title></rect>`;
  }).join('');
  return `<svg class="monitor-chart" viewBox="0 0 ${hourly.length * (width + gap)} ${height}" role="img" aria-label="Failed logins per hour, last 24 hours">${bars}</svg>
    <div class="monitor-chart-labels"><span>${esc(hourly[0]?.hour || '')}</span><span>${esc(hourly[hourly.length - 1]?.hour || '')}</span></div>`;
}

function cardsHtml(cards) {
  const items = [
    ['Successful log-ins', cards.loginsSuccess],
    ['Failed log-ins', cards.loginsFailed],
    ['Accounts locked now', cards.accountsLocked],
    ['IPs blocked now', cards.ipsBlocked],
    ['OTPs sent', cards.otpSent],
    ['OTPs failed', cards.otpFailed],
    ['Alert emails sent', cards.alertsSent]
  ];
  return `<div class="grid stats">${items.map(([label, value]) =>
    `<div class="stat"><div class="label">${esc(label)}</div><div class="num">${esc(value)}</div></div>`).join('')}</div>`;
}

function topIpsHtml(rows) {
  if (!rows.length) return empty('No failed log-ins in the last 24 hours.');
  return `<div class="table-wrap"><table class="table"><thead><tr><th>IP address</th><th>Failures</th><th>Status</th></tr></thead><tbody>${
    rows.map((row) => `<tr><td class="mono">${esc(row.ip)}</td><td>${esc(row.failures)}</td><td>${
      row.blocked ? `<span class="badge badge-red">Blocked ${esc(row.blockedForSeconds)}s</span>` : '<span class="badge badge-gray">Not blocked</span>'
    }</td></tr>`).join('')}</tbody></table></div>`;
}

function flagsHtml(rows) {
  if (!rows.length) return empty('No flags written yet. Run: python scripts/monitor.py');
  return `<div class="table-wrap"><table class="table"><thead><tr><th>Severity</th><th>Pattern</th><th>Target</th><th>Details</th><th>Date</th></tr></thead><tbody>${
    rows.map((row) => `<tr><td><span class="badge badge-${row.severity === 'HIGH' ? 'red' : row.severity === 'MED' ? 'orange' : 'gray'}">${esc(row.severity)}</span></td><td>${esc(row.pattern)}</td><td class="mono">${esc(row.target)}</td><td class="muted">${esc(row.details)}</td><td>${esc(row.flag_date)}</td></tr>`).join('')
  }</tbody></table></div>`;
}

function eventsHtml(rows) {
  if (!rows.length) return empty('No events match the filters.');
  return `<div class="table-wrap"><table class="table"><thead><tr><th>When</th><th>Event</th><th>Username typed</th><th>IP</th><th>Browser</th><th>Details</th></tr></thead><tbody>${
    rows.map((row) => `<tr>
      <td class="muted">${esc(fmt(row.created_at))}</td>
      <td><span class="badge badge-gray">${esc(row.event_type)}</span></td>
      <td>${esc(row.username_typed || '—')}</td>
      <td class="mono">${esc(row.ip_address || '—')}</td>
      <td class="muted small">${esc((row.user_agent || '—').slice(0, 60))}</td>
      <td class="muted">${esc(row.details || '')}</td>
    </tr>`).join('')}</tbody></table></div>`;
}

async function loadMonitorBody() {
  if (state.page !== 'monitor') return;
  const body = $('#monitorBody');
  if (!body) return;
  try {
    const query = monitorQuery();
    const data = await api(`/api/admin/security/summary${query ? `?${query}` : ''}`);

    const select = $('#filterEvent');
    if (select && select.options.length <= 1 && data.eventTypes) {
      data.eventTypes.forEach((type) => {
        const option = document.createElement('option');
        option.value = type;
        option.textContent = type;
        select.appendChild(option);
      });
    }

    body.innerHTML = `
      ${cardsHtml(data.cards)}
      <div class="card monitor-gap">
        <div class="card-title"><h3>Failed log-ins per hour</h3><span class="muted small">Last 24 hours</span></div>
        ${barsSvg(data.hourly || [])}
      </div>
      <div class="monitor-columns">
        <div class="card">
          <div class="card-title"><h3>Top IP addresses</h3><span class="muted small">Most failures in 24 hours</span></div>
          ${topIpsHtml(data.topIps || [])}
        </div>
        <div class="card">
          <div class="card-title"><h3>Flags</h3><span class="muted small">From scripts/monitor.py</span></div>
          ${flagsHtml(data.flags || [])}
        </div>
      </div>
      <div class="card">
        <div class="card-title"><h3>Recent events</h3><span class="muted small">Latest 50 · read-only</span></div>
        ${eventsHtml(data.events || [])}
      </div>
      <p class="muted small">Generated ${esc(data.generatedAt)}. This page never edits or deletes a log row.</p>`;
    animateStatCounters(body);
  } catch (error) {
    body.innerHTML = `<div class="card"><div class="empty">${esc(error.message === 'Access denied.' ? 'Access denied.' : error.message)}</div></div>`;
  }
}
