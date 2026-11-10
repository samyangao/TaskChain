# IT 107 — Secure Registration, Authentication and Monitoring Module

This folder documents the IT 107 final project implemented inside TaskChain.

**System name:** TaskChain

**Stack:** Python / Flask, PostgreSQL (pgAdmin), HTML, CSS, JavaScript. This is the equivalent of the handout's PHP/MySQL stack; get your instructor's written approval for the substitution before Checkpoint 1.

## What was added

| Flow | Where |
|---|---|
| Registration with every core and system field | `app/routes/auth.py`, `app/services/registration_rules.py`, `frontend/pages/register.html`, `frontend/js/pages/register.js` |
| Privacy Notice and consent | `frontend/pages/privacy.html`, `security_profiles.privacy_consent_at` |
| Email OTP (register, login, reset) | `app/services/otp.py`, `app/services/mailer.py` |
| CAPTCHA | `app/services/captcha.py`, `/api/captcha` |
| Three seeded security questions | `app/config.py` (`AUTH_QUESTIONS`) |
| Two-step login and seeded lockout | `app/routes/auth.py`, `app/services/security_controls.py` |
| Forgot and Change Password | `app/routes/password_reset.py`, `frontend/pages/forgot.html`, `frontend/pages/reset-password.html` |
| Security alert emails | `app/services/mailer.py`, `app/services/security_controls.py` |
| Activity log (append-only) | `database/migrations/002_it107_security_module.sql`, `app/services/activity.py` |
| Security monitoring dashboard | `app/routes/monitoring.py`, `frontend/js/pages/monitor.js` |
| Monitoring script | `scripts/monitor.py` |
| Test accounts | `scripts/seed_it107_accounts.py` |

## Setup

1. Copy `.env.example` to `.env` and fill `DB_*`, `FLASK_SECRET_KEY` and `FIELD_ENCRYPTION_KEY`.
2. Apply the schema and migrations:
   ```bat
   scripts\setup_db.bat
   ```
   This runs `database/schema.sql` and both migrations. Migration `002` is safe to run twice.
3. Create the demo accounts:
   ```bat
   python scripts\seed_it107_accounts.py
   ```
4. Configure email (see below), then run:
   ```bat
   python run.py
   ```

### Email

For the demo, use a real Gmail inbox because the instructor will watch the OTP arrive.

1. Turn on 2-Step Verification for the Gmail account.
2. Create an App Password (Google Account → Security → App passwords).
3. Fill `.env`:
   ```
   SMTP_HOST=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USER=your.address@gmail.com
   SMTP_PASSWORD=the16characterapppassword
   SMTP_FROM=your.address@gmail.com
   SMTP_STARTTLS=1
   MAIL_DEV_MODE=0
   ```
4. Send a test: register a new account and confirm the code arrives.

With no SMTP configured and `MAIL_DEV_MODE=1`, codes are written to `logs/mail_outbox.log` (outside the web root) so the flow can be tested offline. **Set `MAIL_DEV_MODE=0` on demo day.**

## Demo flow (matches section 17)

1. Register with one bad input, then correct it. Show the per-field message.
2. Verify with the emailed 6-digit code.
3. Sign in with username/email + password + CAPTCHA, then the emailed code.
4. Fail the password 3 times: show the 15-second countdown, the disabled Log-in and Register links, and the alert email.
5. Use Forgot Password: identify + CAPTCHA → answer Q4/Q7/Q1 → reset OTP → one-time Change Password link.
6. Show the password history rule and the "Your password was changed" email.
7. Run:
   ```bat
   python scripts\monitor.py
   ```
8. Open `/admin/security` as the administrator: cards, 24-hour chart, top IPs, flags, recent events.

## Seeded values (241-01803 → D1 = 0, D2 = 3)

| Parameter | Value |
|---|---|
| Username length | 6–19 |
| Password minimum | 11, maximum 64 |
| Name field maximum | 23 |
| Forgot Password link after | 2 failures |
| Lockout tiers | 15 s at 3, 30 s at 6, 60 s at 9 |
| OTP expiry | 3 minutes |
| Idle timeout | 5 minutes |
| IP block threshold | 11 failures in 10 minutes, blocked for 10 minutes |
| Questions | Q4, Q7, Q1 |

## Tests already run

Run the rule tests with:
```bat
python -m unittest discover -s tests -v
```

- Wrong CAPTCHA on registration is refused by the server (browser test).
- Registration + OTP + login + OTP succeeds (server test).
- Three wrong passwords produce tier 1 (15 s) and an alert email.
- Forgot Password produces a one-time token; the same token is refused the second time.
- Password reset stores the new bcrypt hash and signs out other sessions.
- A requester who calls `/api/admin/security/summary` gets 403 and the attempt is logged as `ADMIN_ACCESS_DENIED`.
- The administrator sees summary cards, 24 buckets, top IPs and recent events.
- `scripts/monitor.py` detects an IP over threshold and does not duplicate the same flag on the same day.
- Contact numbers are unreadable in the database; passwords, answers and OTPs are bcrypt hashes.
- `X-Frame-Options: DENY` and `X-Content-Type-Options: nosniff` are on every response.
- `/scripts/monitor.py` returns 404 in the browser.
