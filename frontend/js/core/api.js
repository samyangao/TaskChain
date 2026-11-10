// ==========================================
// 3. API & NETWORK LAYER
// ==========================================
async function api(url, opts = {}) {
  const { headers, ...rest } = opts;
  const isForm = typeof FormData !== 'undefined' && rest.body instanceof FormData;
  const base = isForm ? { ...(headers || {}) } : { 'Content-Type': 'application/json', ...(headers || {}) };
  const r = await fetch(url, {
    credentials: 'same-origin',
    ...rest,
    headers: typeof withCsrf === 'function' ? withCsrf(base) : base
  });
  
  let d = {};
  try { d = await r.json(); } catch {}
  
  if (r.status === 401) {
    location.href = '/login.html';
    throw Error('Authentication required');
  }
  
  if (!r.ok) throw Error(d.error || 'Request failed');
  return d;
}
