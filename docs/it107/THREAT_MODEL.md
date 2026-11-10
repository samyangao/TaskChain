# Threat Model — Appendix B

One row per protection in section 12. **C, I, A** means which part of the CIA triad the protection mainly defends.

| # | Threat | Vulnerability | Countermeasure | CIA | How I tested it |
|---|---|---|---|---|---|
| 1 | Attacker injects SQL | User input joined into SQL | Prepared statements in every query, including the monitor script; dynamic fragments use allow-listed column names | C, I | `' OR '1'='1` as username returned "Invalid username or password." No SQL error. |
| 2 | Attacker runs script in another user's browser | Unescaped log or profile data | Jinja/`textContent` for static pages; `esc()` for every dynamic dashboard value, including `username_typed` and `user_agent` | C, I | `<script>alert(1)</script>` as username; monitor dashboard rendered it as text. |
| 3 | Attacker submits a forged form | No CSRF token | Per-session CSRF token, `X-CSRF-Token` header checked by a global `before_request`, failures logged as `CSRF_REJECTED` | I | Deleted the token / omitted the header; server returned 403. |
| 4 | Attacker learns which accounts exist | Different messages for unknown user and wrong password | One generic login message; Forgot Password always shows the same seeded questions; lockout message does not mention the account | C | Compared unknown username vs wrong password; identical 401 body. |
| 5 | Attacker sprays many accounts | Unlimited attempts per IP | Persistent `ip_blocks`: 11 failures across any accounts in 10 minutes → 10-minute block; logged as `IP_BLOCKED` | A | Sent failures from one IP; 8th request in the test run hit the accumulated threshold and returned 429. |
| 6 | Attacker reuses a stolen cookie | Long-lived or unhardened session | `HttpOnly`, `SameSite=Lax`, optional `Secure`; session cleared/rotated after login; 5-minute idle timeout; logout clears; `session_version` revokes old cookies | C, I | Waited past 5 minutes; `/api/session/status` returned 401 and the browser redirected to login. |
| 7 | Attacker sets a previously used password | No history | `password_history` keeps the last three bcrypt hashes; current hash is also compared | I | Tried the current password and an older one; "You cannot reuse a recent password." |
| 8 | Bot fills every field | No hidden trap | Off-screen `website` field; if filled, the server returns the normal success message but creates nothing | I | Filled `website` with browser tools; no user row was created. |
| 9 | Attacker's actions cannot be reconstructed | No reliable log | Append-only `activity_log` with event type, username typed, user id, IP, user agent, details, time; DB trigger rejects UPDATE/DELETE | C, I, A | Attempted `UPDATE activity_log`; PostgreSQL raised "append-only". |
| 10 | Attacker reads stack traces | Debug output reaches browser | Central error handlers hide DB/driver messages; rotating `logs/error.log` outside `frontend/` | C | Sent a malformed UUID; received "Invalid identifier format." No traceback. |
| 11 | Attacker finds secrets in Git | Secrets in source | `.env` is gitignored; `.env.example` has placeholders only; startup refuses a short/placeholder `FLASK_SECRET_KEY`; field key is separate | C | Searched tracked files and Git history for the DB password, SMTP password and field key; none found. |
| 12 | Attacker frames the site or sniffs content types | No headers | `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer` on every response | C, I | Checked the network response headers on HTML and API responses. |
| 13 | Database reader sees a sensitive field | Plaintext contact number | `pgcrypto` `pgp_sym_encrypt` (AES-256, random salt/IV); only `/api/me` decrypts it for the owner | C | Queried `security_profiles.contact_number_enc`; 77 bytes of binary, no `0917` prefix. |

## Additional threats covered by the authentication flow

| Threat | Countermeasure |
|---|---|
| Password guessing | bcrypt cost 12; seeded 3-tier lockout (3/6/9 failures → 15/30/60 seconds); server-side `locked_until` |
| OTP brute force | 6-digit `secrets` code, bcrypt hash, 3-minute expiry, 3 attempts then cancel, 60-second resend cooldown, 3 resends per 15 minutes |
| OTP replay | Single-use `consumed_at`; purpose-bound (`register`/`login`/`reset`) |
| Reset link sharing | One-time SHA-256 token, 3-minute expiry, `used_at`, issued only after the emailed code |
| Session fixation | `session.clear()` and a fresh session after login; `session_version` bump on password change |
| Enumeration through registration | ID Number, email and username checks return field-specific messages only after a valid CAPTCHA |
