# Test Accounts

Created by `python scripts/seed_it107_accounts.py` (never through the public registration form). The administrator is inserted directly in the database, as section 13.1 requires.

| Role | Username | Email | Password | Inbox |
|---|---|---|---|---|
| Administrator | `admin12` | `admin12@example.com` | `REDACTED_DEMO_PASSWORD` | `admin12@example.com` |
| Administrator (seed copy) | `it107admin` | `it107.admin@example.com` | `REDACTED_DEMO_PASSWORD` | Replace with an inbox you can open on demo day |
| Requester (user 1) | `it107test1` | `it107.test1@example.com` | `REDACTED_DEMO_PASSWORD` | Replace with an inbox you can open on demo day |
| Requester (user 2) | `it107test2` | `it107.test2@example.com` | `REDACTED_DEMO_PASSWORD` | Replace with an inbox you can open on demo day |

> `admin12@example.com` already existed in this database; its password was reset to `REDACTED_DEMO_PASSWORD` and its username to `admin12`. Sign in with either the username or the email.

## Where the OTP goes while SMTP is not configured

`MAIL_DEV_MODE=1` writes every code to:

```
C:\Users\Administrator\Desktop\TaskChain_2\TaskChain\logs\mail_outbox.log
```

After the password step, open that file and copy the latest `Your log-in code: 123456`. For the real demo, configure Gmail SMTP in `.env` and set `MAIL_DEV_MODE=0` so the code arrives at `admin12@example.com` instead.

The three seeded answers for both requesters are:

- Q4 — What is your mother's maiden first name? → `Maria`
- Q7 — What was the name of your elementary school? → `San Jose Elementary`
- Q1 — What was the name of your first pet? → `Bantay`

## Important before demo day

1. `scripts/seed_it107_accounts.py` uses example.com addresses. Change the `ACCOUNTS` list to real Gmail addresses you control, then re-run the script.
2. Set `MAIL_DEV_MODE=0` and fill the SMTP values in `.env` so codes arrive in a real inbox.
3. Change the demo passwords if your instructor requires unique ones. The seed script stores bcrypt hashes, never plain text.
4. The administrator has no security questions, because administrators are not created through the registration form. Use the requesters for the Forgot Password demo.

## Verification

```bat
python scripts\seed_it107_accounts.py
python scripts\monitor.py
```

Then open `http://127.0.0.1:5000/login.html` and sign in with `it107admin`.
