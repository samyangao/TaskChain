# SecuritySys — Activity 2 Flask Integration

This package integrates the supplied `lab_test.php` functionality into the existing Flask SecuritySys project and follows the supplied IT107 Activity 2 PDF.

## What was integrated

- Converted `lab_test.php` into a Flask-controlled laboratory tester.
- Added `/lab` as the Cyber Lab UI.
- Added `/api/lab-test/stream` for streaming test results.
- Localhost-only target validation.
- Activity wordlist:
  - 13 common passwords.
  - 5-digit values `00000` through `05000`.
  - Total: 5,014 candidates.
- Compatible with the existing `/api/login` JSON Flask endpoint.
- Preserves the activity's metrics: attempts, elapsed time, HTTP status, discovered password / blocked result.
- Existing Flask login defense includes 5 failed attempts + 5-minute temporary lockout.
- Added `lab_setup.py` to create/reset the `admin12@example.com` lab account.

## Important activity workflow

### Phase 1 — Setup

1. Install PostgreSQL and create the database named in `.env`.
2. Run `schema.sql`.
3. Copy `.env.example` to `.env` and fill in PostgreSQL credentials.
4. Create the Python environment:
   `python -m venv venv`
5. Activate:
   `venv\Scripts\activate`
6. Install:
   `pip install -r requirements.txt`
7. Prepare the lab account with the password `05000`:
   `python lab_setup.py --password 05000`
8. Start Flask:
   `python app.py`
9. Open:
   `http://127.0.0.1:5000/lab`

### Phase 2 — Controlled unprotected test

The supplied activity requires an unprotected login for the first test. Because this project already contains defensive lockout logic, use the local lab switch only for this classroom phase.

In a Windows Command Prompt before starting Flask:
`set LAB_UNPROTECTED=1`
then:
`python app.py`

Run the tester at `/lab` against:
`http://127.0.0.1:5000/api/login`
Email: `admin12@example.com`

With password `05000`, the tester will try the candidates in the required order and should eventually reach `05000`.

Take a screenshot showing:
- terminal output
- total attempts
- elapsed time
- discovered password
- HTTP status

### Phase 3 — Protected test

Stop Flask and start it without the lab switch:
`python app.py`

Reset the account before the protected test:
`python lab_setup.py --password 05000`

Run `/lab` again.

After 5 failed attempts, the login API returns HTTP 429 and the tester reports `BLOCKED / RATE-LIMITED`. Capture this screenshot.

## Why the lab stops on HTTP 429

Once the defense has clearly intercepted automated authentication, continuing thousands of requests would not add useful evidence for the activity and would create unnecessary load. The tester therefore stops when the protected target returns 429.

## Submission report

The supplied PDF asks for one PDF containing:
1. Screenshots for unprotected and protected tests.
2. Execution metrics for both.
3. Analysis/reflection about rate limiting, account lockout, and CAPTCHA.
4. Professional formatting.

Use the screenshots you actually obtain from your run; do not invent metrics.

## Security note

This tester intentionally sends candidate passwords only to localhost and is designed for the supplied classroom laboratory. Do not change the target validation to permit public or third-party hosts.
