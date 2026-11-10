// CSRF helper. The server sets a readable csrf_token cookie; every state-
// changing request must echo it in the X-CSRF-Token header. A cross-site page
// can send a request but cannot read this cookie, so it cannot forge the header.
function csrfToken() {
  const match = document.cookie.match(/(?:^|; )csrf_token=([^;]*)/);
  return match ? decodeURIComponent(match[1]) : '';
}

function withCsrf(headers = {}) {
  const token = csrfToken();
  return token ? { ...headers, 'X-CSRF-Token': token } : { ...headers };
}

async function secureFetch(url, opts = {}) {
  const { headers, ...rest } = opts;
  const isForm = typeof FormData !== 'undefined' && rest.body instanceof FormData;
  const base = isForm ? { ...(headers || {}) } : { 'Content-Type': 'application/json', ...(headers || {}) };
  return fetch(url, {
    credentials: 'same-origin',
    ...rest,
    headers: withCsrf(base)
  });
}
