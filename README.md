# TaskChain

**TaskChain: An Integrated Multi-Party Task Handover and Service Completion Management System**

TaskChain is a Flask + PostgreSQL web application that tracks a task from request through assignment, processing, handover, evidence, verification, and completion. It preserves the original SecuritySys authentication/security foundation and extends it into the full TaskChain workflow.

## Stack
- Python / Flask REST API
- PostgreSQL + psycopg
- HTML, CSS, JavaScript
- bcrypt authentication
- Server-side sessions

## Quick start (Windows)

1. Open Command Prompt in this folder.
2. Activate the existing environment:
   `venv\\Scripts\\activate`
3. If dependencies are missing:
   `python -m pip install -r requirements.txt`
4. Create/update the PostgreSQL database using `schema.sql`.
5. Check `.env` and set DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD and a strong FLASK_SECRET_KEY.
6. Create the controlled administrator/lab account if needed:
   `python lab_setup.py --password 05000`
7. Start Flask:
   `python app.py`
8. Open `http://127.0.0.1:5000/`

## Roles
Public registration creates `requester` accounts. An administrator can change roles in **Users** to:
- requester
- coordinator
- personnel
- verifier
- administrator

The included `lab_setup.py` resets `admin12@example.com` as an administrator for the existing classroom security activity.

## Core flow
Login → Dashboard → New Request → Review/Assignment → Accept → Processing → Handover → Evidence → Verification → Completed → Audit/Reports.

## PostgreSQL migration
The schema is intentionally written to preserve an existing `users` and `login_attempts` foundation. Run the full `schema.sql` against the same PostgreSQL database. It creates the TaskChain tables and adds the `role` field to an older users table when necessary.

## Evidence uploads
Uploaded evidence is stored in the local `uploads/` folder. The application validates file extensions and keeps the evidence record linked to its task and uploader. For production deployment, move file storage to controlled object storage and add stronger content scanning and authorization rules.

## Security
The application keeps bcrypt hashing, generic login failures, failed-login lockout, authenticated sessions, role-based authorization, parameterized SQL, and audit logging. Do not commit `.env` or real passwords.

## Existing classroom lab
The original localhost-only Activity 2 page remains available at `/lab` and `static/lab_test.html`.
