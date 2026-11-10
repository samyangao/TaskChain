"""Session start/finish and TOTP key helpers used by the auth routes."""

import hashlib
from datetime import datetime, timezone

from flask import current_app, session

from app.services.activity import log_event
from app.services.audit import audit
from app.utils import client_ip


def _totp_db_key():
    """Key used by PostgreSQL pgp_sym_encrypt/decrypt for TOTP secrets."""
    return hashlib.sha256(("taskchain-totp:" + current_app.secret_key).encode()).hexdigest()


def _start_session(user, remember=False):
    # Keep the CSRF token: it is the one thing that must survive a login
    # rotation, otherwise the very next POST from the page would fail.
    csrf = session.get("csrf_token")
    session.clear()
    if csrf:
        session["csrf_token"] = csrf
    session["user_id"] = str(user["id"])
    session["sv"] = int(user["session_version"] or 0)
    session["login_at"] = datetime.now(timezone.utc).isoformat()
    session["last_activity"] = datetime.now(timezone.utc).isoformat()
    session.permanent = bool(remember)


def _finish_login(cur, user, remember=False):
    cur.execute(
        "UPDATE users SET failed_login_attempts=0, lockout_tier=0, locked_until=NULL, "
        "last_login_at=now() WHERE id=%s",
        (user["id"],),
    )
    cur.execute(
        "INSERT INTO login_attempts(email,success,ip_address) VALUES(%s,%s,%s)",
        (user["email"], True, client_ip()),
    )
    audit(cur, user["id"], "login_success", "user", user["id"], "Successful login")
    log_event(cur, "LOGIN_SUCCESS", username_typed=user.get("username") or user["email"],
              user_id=user["id"], details="Password and one-time code accepted")
    _start_session(user, remember)
