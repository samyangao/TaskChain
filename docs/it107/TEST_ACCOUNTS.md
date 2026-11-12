# Test Accounts

Created by `python scripts/seed_it107_accounts.py` (never through the public registration form). The administrator is inserted directly in the database, as section 13.1 requires.

| Role | Username | Email | Password | Inbox |
|---|---|---|---|---|
| Administrator | `it107admin` | `it107.admin@example.com` | `SEED_ADMIN_PASSWORD` in `.env` | Replace with an inbox you can open on demo day |
| Requester (user 1) | `it107test1` | `it107.test1@example.com` | `SEED_USER1_PASSWORD` in `.env` | Replace with an inbox you can open on demo day |
| Requester (user 2) | `it107test2` | `it107.test2@example.com` | `SEED_USER2_PASSWORD` in `.env` | Replace with an inbox you can open on demo day |

> The public repository deliberately does not contain the demo passwords. The values are in the local `.env` and in the private submission sheet. Never commit `.env` or the private sheet.

> On the demo machine, set `SEED_ADMIN_EMAIL`, `SEED_USER1_EMAIL` and `SEED_USER2_EMAIL` in `.env` to real inboxes (Gmail plus-aliases work well). The seed script reads them; the public repository keeps the `example.com` placeholders.

## Where the OTP goes while SMTP is not configured

`MAIL_DEV_MODE=1` writes every code to:

```
C:\Users\Administrator\Desktop\TaskChain_2\TaskChain\logs\mail_outbox.log
```

After the password step, open that file and copy the latest `Your log-in code: 123456`. For the real demo, configure Gmail SMTP in `.env` and set `MAIL_DEV_MODE=0` so the code arrives at the inbox configured in `SMTP_USER` instead.

The three seeded answers for both requesters are:

- Q4 — What is your mother's maiden first name? → `Maria`
- Q7 — What was the name of your elementary school? → `San Jose Elementary`
- Q1 — What was the name of your first pet? → `Bantay`

## Important before demo day

1. `scripts/seed_it107_accounts.py` defaults to example.com addresses. On the demo machine, set `SEED_ADMIN_EMAIL`, `SEED_USER1_EMAIL` and `SEED_USER2_EMAIL` in `.env`, then re-run the script.
2. Set `MAIL_DEV_MODE=0` and fill the SMTP values in `.env` so codes arrive in a real inbox.
3. Set `SEED_ADMIN_PASSWORD`, `SEED_USER1_PASSWORD` and `SEED_USER2_PASSWORD` in `.env` before running the seed script. The seed script stores bcrypt hashes and refuses to run if the values are missing.
4. The administrator has no security questions, because administrators are not created through the registration form. Use the requesters for the Forgot Password demo.

## Verification

```bat
python scripts\seed_it107_accounts.py
python scripts\monitor.py
```

Then open `http://127.0.0.1:5000/login.html` and sign in with `it107admin`.
