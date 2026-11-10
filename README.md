# TaskChain

**A secure multi-party task handover and service completion system.**

A Flask + PostgreSQL web application that tracks a task from request through assignment, processing, handover, evidence, verification and completion.

## Stack
- Python / Flask REST API (Blueprints)
- PostgreSQL + psycopg
- HTML, CSS, JavaScript (no build step)
- bcrypt authentication, server-side sessions, optional TOTP

## Project structure

```
TaskChain/
├── run.py                  # entry point:  python run.py
├── app/                    # backend
│   ├── __init__.py         #   create_app()
│   ├── config.py           #   paths, env flags, constants
│   ├── db.py, utils.py, permissions.py, errors.py, hooks.py, log.py
│   ├── routes/             #   one Blueprint per feature (auth, tasks, assignment, ...)
│   └── services/           #   business logic (sla_engine, custody_chain, handovers, ...)
├── frontend/               # everything the browser loads
│   ├── pages/              #   login, register, dashboard, lab_test (.html)
│   ├── css/                #   main.css imports base/ layout/ components/ pages/
│   └── js/                 #   core/ components/ pages/ vendor/  (plain <script> tags, loaded in order)
├── database/
│   ├── schema.sql          #   base tables
│   └── migrations/         #   numbered, re-runnable SQL files
├── scripts/                # run.bat, setup_db.bat, lab_setup.py
├── docs/activity-2/        # classroom lab notes and report template
├── uploads/                # runtime evidence files (git-ignored)
└── tests/
```

## Quick start (Windows)

1. Copy `.env.example` to `.env` and set `DB_*` and a strong `FLASK_SECRET_KEY`.
2. Create the database schema: run `scripts\setup_db.bat` (applies `database/schema.sql`, then every file in `database/migrations/`).
3. Start the app: `scripts\run.bat` (creates `venv`, installs `requirements.txt`, runs `python run.py`).
4. Open `http://127.0.0.1:5000/`.

Optional lab/admin account: `python scripts/lab_setup.py --password <password>`.

## Adding things
- **New API feature:** add `app/routes/<feature>.py` with a `bp = Blueprint(...)`, then add it to `app/routes/__init__.py`.
- **New business rule:** put it in `app/services/`, not in a route file.
- **New page script:** add `frontend/js/pages/<page>.js` and a `<script>` line in `frontend/pages/dashboard.html` before `main.js`.
- **New database change:** add `database/migrations/00N_<name>.sql` (make it safe to run twice).

## Roles
Public registration creates `requester` accounts. An administrator can change roles in **Users**: requester, coordinator, personnel, verifier, administrator.

## Core flow
Login → Dashboard → New Request → Review/Assignment → Accept → Processing → Handover → Evidence → Verification → Completed → Audit/Reports.

## Security notes
bcrypt hashing, generic login failures, failed-login lockout, role-based authorization, parameterized SQL, audit logging. Never commit `.env`. Uploaded evidence stays in `uploads/` (runtime data, not source).

## IT 107 security module
The final project's secure registration, email OTP, CAPTCHA, seeded lockout, Forgot/Change Password, activity log, monitoring dashboard and `scripts/monitor.py` live alongside the task workflow. See `docs/it107/README_IT107.md` for setup, demo steps, the seed table and test accounts. Apply `database/migrations/002_it107_security_module.sql` (or re-run `scripts\setup_db.bat`) before starting the app.

## Classroom lab
The Activity 2 page is available at `/lab` only when `ENABLE_LAB=1`. See `docs/activity-2/`.
