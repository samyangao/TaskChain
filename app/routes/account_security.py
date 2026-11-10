"""Account security: password, TOTP and session controls; login-attempt log."""

import bcrypt
import re
from app.services.totp import generate_secret, provisioning_uri, verify_code
from flask import Blueprint, jsonify, request, session
from app.db import db
from app.permissions import login_required, roles_required
from app.services.activity import log_event
from app.services.audit import audit
from app.services.auth_service import _totp_db_key
from app.services.mailer import send_password_changed
from app.services.notifications import notify
from app.services.registration_rules import password_strength, validate_password
from app.services.security_controls import is_recent_password, remember_password
from app.utils import client_ip, ip_throttled, json_error

bp = Blueprint("account_security", __name__)


@bp.get("/api/security/overview")
@login_required
def security_overview(user):
    return jsonify(
        totp_enabled=bool(user["totp_enabled"]),
        password_changed_at=user["password_changed_at"].isoformat() if user.get("password_changed_at") else None,
        session_started_at=session.get("login_at"),
        session_version=user["session_version"],
    )


@bp.post("/api/security/password")
@login_required
def change_password(user):
    retry_after = ip_throttled("change_password", limit=10, window=300)
    if retry_after:
        return jsonify(error="Too many password changes. Please try again later.", retryAfterSeconds=retry_after), 429
    data = request.get_json(silent=True) or {}
    current = data.get("currentPassword") or ""
    new = data.get("newPassword") or ""
    confirm = data.get("confirmPassword") or ""
    if not current or not new:
        return json_error("Enter your current password and a new password.")
    if new != confirm:
        return json_error("Mismatch Password.")
    message = validate_password(new, confirm)
    if message:
        return json_error(message)
    if new == current:
        return json_error("You cannot reuse a recent password.")
    with db() as conn, conn.cursor() as cur:
        cur.execute("SELECT password_hash,session_version FROM users WHERE id=%s", (user["id"],))
        row = cur.fetchone()
        if not row or not bcrypt.checkpw(current.encode(), row["password_hash"].encode()):
            return json_error("Your current password is not correct.", 401)
        if is_recent_password(cur, user["id"], new):
            return json_error("You cannot reuse a recent password.")
        new_hash = bcrypt.hashpw(new.encode(), bcrypt.gensalt(rounds=12)).decode()
        cur.execute(
            """UPDATE users
               SET password_hash=%s, password_changed_at=now(), session_version=session_version+1
               WHERE id=%s RETURNING session_version""",
            (new_hash, user["id"]),
        )
        new_version = cur.fetchone()["session_version"]
        remember_password(cur, user["id"], new_hash)
        log_event(cur, "PASSWORD_CHANGED", username_typed=user.get("username") or user["email"],
                  user_id=user["id"], details="Password changed from the account security page")
        audit(cur, user["id"], "password_changed", "user", user["id"], "Password changed; all other sessions signed out")
        notify(cur, user["id"], "Password changed",
               "Your TaskChain password was changed. If this was not you, contact an administrator immediately.",
               None, "security")
        sent = send_password_changed(user["email"], client_ip(), request.headers.get("User-Agent", ""))
        if sent:
            log_event(cur, "ALERT_EMAIL_SENT", username_typed=user.get("username") or user["email"],
                      user_id=user["id"], details="Password changed notification emailed")
        # Keep this browser signed in, but invalidate every other cookie.
        session["sv"] = int(new_version)
    return jsonify(message="Successfully Change Password.")


@bp.post("/api/security/totp/setup")
@login_required
def totp_setup(user):
    retry_after = ip_throttled("totp_setup", limit=10, window=300)
    if retry_after:
        return jsonify(error="Too many attempts. Please try again later.", retryAfterSeconds=retry_after), 429
    data = request.get_json(silent=True) or {}
    password = data.get("password") or ""
    with db() as conn, conn.cursor() as cur:
        cur.execute("SELECT password_hash,totp_enabled,email FROM users WHERE id=%s", (user["id"],))
        row = cur.fetchone()
        if not bcrypt.checkpw(password.encode(), row["password_hash"].encode()):
            return json_error("Your password is not correct.", 401)
        if row["totp_enabled"]:
            return json_error("Two-factor authentication is already enabled. Disable it first to set up a new device.", 409)
        secret = generate_secret()
        cur.execute(
            "UPDATE users SET totp_pending_secret=pgp_sym_encrypt(%s,%s), totp_last_step=NULL WHERE id=%s",
            (secret, _totp_db_key(), user["id"]),
        )
        audit(cur, user["id"], "totp_setup_started", "user", user["id"], "Authenticator setup started")
    return jsonify(
        secret=secret,
        otpauthUri=provisioning_uri(secret, row["email"]),
        account=row["email"],
        issuer="TaskChain",
    )


@bp.post("/api/security/totp/enable")
@login_required
def totp_enable(user):
    retry_after = ip_throttled("totp_enable", limit=15, window=300)
    if retry_after:
        return jsonify(error="Too many attempts. Please try again later.", retryAfterSeconds=retry_after), 429
    code = re.sub(r"\s+", "", str((request.get_json(silent=True) or {}).get("code") or ""))
    if not re.fullmatch(r"\d{6}", code):
        return json_error("Enter the 6-digit code from your authenticator app.")
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT totp_enabled,
                      CASE WHEN totp_pending_secret IS NULL THEN NULL
                           ELSE pgp_sym_decrypt(totp_pending_secret,%s)::text END AS pending
               FROM users WHERE id=%s""",
            (_totp_db_key(), user["id"]),
        )
        row = cur.fetchone()
        if row["totp_enabled"]:
            return json_error("Two-factor authentication is already enabled.", 409)
        if not row["pending"]:
            return json_error("Start the authenticator setup again; no pending secret was found.", 409)
        ok, step = verify_code(row["pending"], code)
        if not ok:
            return json_error("That code is not correct. Check your authenticator app and try again.")
        cur.execute(
            """UPDATE users
               SET totp_secret=totp_pending_secret, totp_pending_secret=NULL, totp_enabled=TRUE,
                   totp_enabled_at=now(), totp_last_step=NULL
               WHERE id=%s""",
            (user["id"],),
        )
        audit(cur, user["id"], "totp_enabled", "user", user["id"], "Two-factor authentication enabled")
        notify(cur, user["id"], "Two-factor authentication enabled",
               "Your account now requires an authenticator code at sign-in.", None, "security")
    return jsonify(message="Two-factor authentication is enabled.")


@bp.post("/api/security/totp/disable")
@login_required
def totp_disable(user):
    retry_after = ip_throttled("totp_disable", limit=10, window=300)
    if retry_after:
        return jsonify(error="Too many attempts. Please try again later.", retryAfterSeconds=retry_after), 429
    data = request.get_json(silent=True) or {}
    password = data.get("password") or ""
    code = re.sub(r"\s+", "", str(data.get("code") or ""))
    if not re.fullmatch(r"\d{6}", code):
        return json_error("Enter the current 6-digit code from your authenticator app.")
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT password_hash,totp_enabled,
                      CASE WHEN totp_secret IS NULL THEN NULL
                           ELSE pgp_sym_decrypt(totp_secret,%s)::text END AS secret
               FROM users WHERE id=%s""",
            (_totp_db_key(), user["id"]),
        )
        row = cur.fetchone()
        if not bcrypt.checkpw(password.encode(), row["password_hash"].encode()):
            return json_error("Your password is not correct.", 401)
        if not row["totp_enabled"] or not row["secret"]:
            return json_error("Two-factor authentication is not enabled.", 409)
        ok, _ = verify_code(row["secret"], code)
        if not ok:
            return json_error("That code is not correct. Check your authenticator app and try again.")
        cur.execute(
            """UPDATE users
               SET totp_enabled=FALSE, totp_secret=NULL, totp_pending_secret=NULL, totp_last_step=NULL,
                   totp_enabled_at=NULL, session_version=session_version+1
               WHERE id=%s RETURNING session_version""",
            (user["id"],),
        )
        new_version = cur.fetchone()["session_version"]
        session["sv"] = int(new_version)
        audit(cur, user["id"], "totp_disabled", "user", user["id"], "Two-factor authentication disabled; other sessions signed out")
        notify(cur, user["id"], "Two-factor authentication disabled",
               "Your account no longer requires an authenticator code. If this was not you, contact an administrator.",
               None, "security")
    return jsonify(message="Two-factor authentication is disabled. Your other sessions have been signed out.")


@bp.post("/api/security/sign-out-everywhere")
@login_required
def sign_out_everywhere(user):
    with db() as conn, conn.cursor() as cur:
        cur.execute("UPDATE users SET session_version=session_version+1 WHERE id=%s", (user["id"],))
        audit(cur, user["id"], "signed_out_everywhere", "user", user["id"], f"All sessions revoked from {client_ip()}")
    session.clear()
    return jsonify(message="Signed out on every device.")


@bp.get("/api/security/login-attempts")
@login_required
@roles_required("administrator")
def login_attempts(user):
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT l.id, l.email, l.success, l.ip_address, l.attempted_at,
                      u.full_name AS user_name, u.role, u.failed_login_attempts,
                      u.locked_until
               FROM login_attempts l
               LEFT JOIN users u ON u.email = l.email
               ORDER BY l.attempted_at DESC LIMIT 200"""
        )
        rows = cur.fetchall()
        # Summary: currently locked accounts
        cur.execute(
            """SELECT id, full_name, email, role, failed_login_attempts, locked_until
               FROM users
               WHERE locked_until IS NOT NULL AND locked_until > now()
               ORDER BY locked_until DESC"""
        )
        locked = cur.fetchall()
    attempts = [
        {
            "id": str(r["id"]),
            "email": r["email"],
            "user_name": r["user_name"] or "Unknown",
            "role": r["role"] or "—",
            "success": r["success"],
            "ip_address": str(r["ip_address"]) if r["ip_address"] else "—",
            "attempted_at": r["attempted_at"].isoformat() if hasattr(r["attempted_at"], "isoformat") else str(r["attempted_at"]),
            "failed_login_attempts": r["failed_login_attempts"] or 0,
            "locked_until": r["locked_until"].isoformat() if r["locked_until"] and hasattr(r["locked_until"], "isoformat") else (str(r["locked_until"]) if r["locked_until"] else None),
        }
        for r in rows
    ]
    locked_accounts = [
        {
            "id": str(r["id"]),
            "full_name": r["full_name"],
            "email": r["email"],
            "role": r["role"],
            "failed_login_attempts": r["failed_login_attempts"],
            "locked_until": r["locked_until"].isoformat() if hasattr(r["locked_until"], "isoformat") else str(r["locked_until"]),
        }
        for r in locked
    ]
    return jsonify(attempts=attempts, locked_accounts=locked_accounts)
