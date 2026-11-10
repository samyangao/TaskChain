# Design Decisions (P4)

Every "Your call" in the handout is answered below with the reasoning used in the implementation.

## 1. Password hashing algorithm (§4.4)

I use **bcrypt with cost 12** (`bcrypt.hashpw(..., bcrypt.gensalt(rounds=12))`). bcrypt is deliberately slow and memory-hard enough to make offline guessing expensive, it salts every hash automatically, and it is available in the Python ecosystem without a custom construction. Cost 12 takes roughly a quarter of a second on the lab machine — slow enough to hurt an attacker, fast enough that a normal login is not noticeable. I did not use SHA-256 because a fast hash lets a GPU test billions of candidates per second. Passwords are never stored, logged or emailed in plain text.

## 2. What makes a password strong (§4.9)

The strength meter and the server use the same rule: count the character classes present (lowercase, uppercase, digit, symbol). A password is **Weak** when it is shorter than the seeded 11 characters or uses at most one class; **Medium** when it meets the length and uses two classes; **Strong** when it meets the length and uses three or more. Weak is rejected by both the browser and the server. This is a deliberate simplification of zxcvbn: it is explainable during the demo and it enforces length plus variety, which are the two properties that matter most for resisting guessing. A long passphrase with three classes is accepted even if it has no symbol, because length dominates.

## 3. Why hash a security answer (§5)

A security answer is a password by another name: if it were stored as text, anyone who read the database could use it to reset the account, and people often reuse the same answer on other sites. I lowercase the answer before hashing so "Bantay" and "bantay" match, then store a bcrypt hash. The trade-off is that the system cannot show the answer back to the user; that is the point. Because bcrypt is intentionally slow, a stolen answer table is expensive to attack.

## 4. Does a failed CAPTCHA count as a failed login? (§7)

**Not against the account, but yes against the IP.** A wrong CAPTCHA is logged as `CAPTCHA_FAILED` and feeds the 10-minute IP threshold, because a machine that fails CAPTCHAs repeatedly is exactly the traffic the IP block exists to stop. It does **not** increment `users.failed_login_attempts`, because a typo in a distorted image should not lock a legitimate user out of their account. This keeps the account lockout meaningful (it measures password guessing) while still making automated abuse expensive.

## 5. Is disabling the back button enough? (§8.4)

No. The back button is a browser convenience; a user can clear cookies, open a new tab, or replay the request with a tool. The real protection is server-side: every protected endpoint calls `current_user()`, which checks the session, the `session_version` and the idle timestamp before returning any data. Logout clears the session, and password changes bump `session_version`, so an old cookie stops working immediately. I also send `Cache-Control`-friendly responses and the frontend redirects on 401, but that is cosmetic; the server check is what protects the page.

## 6. How does the verified user reach Change Password? (§10)

The server remembers the completed steps in two places. The short-lived session flags (`reset_user`, `reset_stage`, `reset_at`) prove that identify and answer succeeded. After the reset OTP is accepted, the server creates a row in `password_reset_tokens` with a SHA-256 hash of a 32-byte random token, a 3-minute expiry and `used_at = NULL`, and returns the token in the reset URL. The Change Password page sends the token to `/api/reset-password`; the server hashes it, checks that it is unused and unexpired, and marks it used in the same transaction that changes the password. Opening `/reset-password.html` with no token, an old token, or a used token is refused by `/api/reset/validate` and by the POST. The token is never stored in plain text.

## 7. Protecting the log itself (§13)

The database account used by the app should **not** be allowed to delete rows from the log table. I enforce the stronger version in PostgreSQL itself: `activity_log`, `audit_logs` and `custody_chain` have a `BEFORE UPDATE OR DELETE` trigger that raises an exception, so even a normal application account cannot rewrite history. The app only ever runs `INSERT` and `SELECT` on `activity_log`. A database owner can disable a trigger, which is why the custody chain also keeps a SHA-256 hash chain: tampering is detectable even by someone with enough privilege to disable the trigger. For deployment I would create a separate PostgreSQL role for the app with `INSERT, SELECT` on the log and no `UPDATE/DELETE`.

## 8. Running the monitor automatically (§14)

On Windows I would create a Task Scheduler task that runs every 15 minutes:
```
Program:   C:\path\to\venv\Scripts\python.exe
Arguments: scripts\monitor.py
Start in:  C:\path\to\TaskChain
```
On Linux the equivalent is a cron entry:
```
*/15 * * * * cd /path/to/TaskChain && /path/to/venv/bin/python scripts/monitor.py >> logs/monitor.log 2>&1
```
The script is idempotent for a day: the unique key `(pattern, target, flag_date)` means a repeated run updates nothing and reports the finding as "already flagged today". During the demo I run it by hand so the instructor can see the console output.

## 9. Can a JavaScript file really be hidden? (§15)

No. A browser loading `js/validate.js` with a `<script>` tag sends the same HTTP request as a person typing that address. The server cannot tell the two apart, and if it blocked the file the page would break. What I did is keep no secrets in JavaScript: validation messages are duplicated on the server, the CAPTCHA answer is in the server session, the CSRF token is per-session, and the database/SMTP/encryption keys are in `.env` outside `frontend/`. Blocking directory listing and returning 404 for `/scripts/monitor.py` protects the things that genuinely must not be public; it does not pretend that a stylesheet or validation script is secret.

## 10. Hashing is not encryption (§12 note)

A hash is one-way: I use bcrypt for passwords, security answers and OTPs because I only ever need to compare a candidate, never to display the original. Encryption is reversible: the Contact Number must be shown back to its owner, so I encrypt it with pgcrypto's AES-256 (`pgp_sym_encrypt`) and decrypt it only in `/api/me` for the logged-in owner. If an attacker steals the database but not the key, the contact number is unreadable; if I had hashed it, I could never show it again.

## 11. Why email OTP instead of an authenticator app?

The handout requires the OTP to be emailed, to expire after the seeded number of minutes, to be single-use and to be visible in the instructor's inbox during the demo. A TOTP authenticator app would satisfy "second factor" but not the email, expiry or demo requirements. The existing TaskChain TOTP feature remains available as an extra account-security option, but the graded login path uses the email OTP.

## 12. Stack substitution

The project stays on Flask + PostgreSQL rather than PHP + MySQL. The handout's mechanisms map one-to-one: `random_int` → `secrets`, `password_hash` → bcrypt, `$_SESSION` → Flask signed session, PHPMailer → `smtplib`, PHP GD → the pure-Python PNG CAPTCHA, `openssl_encrypt` → pgcrypto AES-256, `php scripts/monitor.php` → `python scripts/monitor.py`. The security properties being graded are the same. The instructor's written approval for the substitution is required before Checkpoint 1.

## 13. IP blocking persistence

The old in-process throttle disappears when Flask restarts, so it cannot be the authoritative block. I added `ip_blocks` in PostgreSQL. Login, Forgot Password identify and Forgot Password answer all check it before doing any work, and the failure counter reads the append-only `activity_log`, so a restart does not reset an attacker's progress. The in-process throttle remains as a cheap first line of defence for non-security endpoints.
