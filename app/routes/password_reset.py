"""Forgot Password and one-time reset flow (handout sections 10 and 11)."""

import bcrypt
import hashlib
import re
import secrets
from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify, request, session

from app.config import AUTH_QUESTION_NUMBERS, AUTH_QUESTIONS, RESET_TOKEN_MINUTES
from app.db import db
from app.services.activity import log_event, now_utc, pht_string
from app.services.captcha import check_captcha
from app.services.mailer import dev_mail_mode, send_otp_email, send_password_changed
from app.services.otp import issue_otp, verify_otp
from app.services.registration_rules import password_strength, validate_answer, validate_password
from app.services.security_controls import (
    apply_failed_login,
    clear_failures,
    ip_block_remaining,
    is_recent_password,
    record_otp_failure,
    record_unknown_failure,
    remember_password,
)
from app.utils import client_ip, ip_throttled, json_error, parse_uuid

bp = Blueprint("password_reset", __name__)

GENERIC_ANSWER_ERROR = "That answer is not correct."


def _forgot_session(max_minutes=15):
    identifier = session.get("forgot_identifier")
    started = session.get("forgot_at")
    if not identifier or not started:
        return None
    try:
        when = datetime.fromisoformat(started)
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None
    if now_utc() - when > timedelta(minutes=max_minutes):
        return None
    return identifier


def _reset_session(max_minutes=15):
    user_id = session.get("reset_user")
    started = session.get("reset_at")
    if not user_id or not parse_uuid(user_id) or not started:
        return None
    try:
        when = datetime.fromisoformat(started)
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None
    if now_utc() - when > timedelta(minutes=max_minutes):
        return None
    return user_id


def _find_user(cur, identifier):
    cur.execute(
        """SELECT id,full_name,email,username,is_active,is_verified,failed_login_attempts,
                  locked_until,lockout_tier
             FROM users WHERE username=%s OR email=%s LIMIT 1""",
        (identifier, identifier),
    )
    return cur.fetchone()


# ---------------------------------------------------------------------------
# Step 1: identify + CAPTCHA. Always show the same three seeded questions.
# ---------------------------------------------------------------------------
@bp.post("/api/forgot/identify")
def forgot_identify():
    retry = ip_throttled("forgot_identify", limit=15, window=300)
    if retry:
        return jsonify(error="Too many attempts. Please try again later.",
                       retryAfterSeconds=retry), 429

    data = request.get_json(silent=True) or {}
    identifier = (data.get("identifier") or "").strip()
    if not identifier:
        return json_error("Enter your username or email.")

    if not check_captcha(data.get("captcha")):
        with db() as conn, conn.cursor() as cur:
            log_event(cur, "CAPTCHA_FAILED", username_typed=identifier,
                      details="Forgot Password CAPTCHA was missing or wrong")
        return json_error("The CAPTCHA code is not correct. Please try again.", 400)

    with db() as conn, conn.cursor() as cur:
        remaining = ip_block_remaining(cur, client_ip())
        if remaining:
            return jsonify(error="Too many failed attempts from this address. Please try again later.",
                           retryAfterSeconds=remaining, ipBlocked=True), 429
        user = _find_user(cur, identifier)
        log_event(cur, "RESET_REQUESTED", username_typed=identifier,
                  user_id=user["id"] if user else None,
                  details="Forgot Password started")

    session["forgot_identifier"] = identifier
    session["forgot_user"] = str(user["id"]) if user else ""
    session["forgot_at"] = now_utc().isoformat()

    # The three questions are the same for every account because they come from
    # the seed, so showing them does not reveal whether the username exists.
    return jsonify(
        message="Choose one of your security questions and enter your answer.",
        questions=[{"number": n, "question": q} for n, q in AUTH_QUESTIONS],
    )


# ---------------------------------------------------------------------------
# Step 2: answer the question. A wrong answer uses the same lockout as login.
# ---------------------------------------------------------------------------
@bp.post("/api/forgot/answer")
def forgot_answer():
    retry = ip_throttled("forgot_answer", limit=15, window=300)
    if retry:
        return jsonify(error="Too many attempts. Please try again later.",
                       retryAfterSeconds=retry), 429

    identifier = _forgot_session()
    if not identifier:
        return json_error("Your reset session expired. Start again.", 401)

    data = request.get_json(silent=True) or {}
    try:
        question_no = int(data.get("questionNo"))
    except (TypeError, ValueError):
        return json_error("Choose one of your security questions.")
    if question_no not in AUTH_QUESTION_NUMBERS:
        return json_error("Choose one of your security questions.")

    answer = str(data.get("answer") or "").strip()
    confirm = str(data.get("confirmAnswer") or "").strip()
    message = validate_answer(answer)
    if message:
        return json_error(message)
    if answer.lower() != confirm.lower():
        return json_error("Answers do not match.")

    with db() as conn, conn.cursor() as cur:
        remaining = ip_block_remaining(cur, client_ip())
        if remaining:
            return jsonify(error="Too many failed attempts from this address. Please try again later.",
                           retryAfterSeconds=remaining, ipBlocked=True), 429
        user = _find_user(cur, identifier)
        if not user or not user["is_active"]:
            cur.execute("INSERT INTO login_attempts(email,success,ip_address) VALUES(%s,%s,%s)",
                        (identifier, False, client_ip()))
            record_unknown_failure(cur, identifier)
            return json_error(GENERIC_ANSWER_ERROR, 401)

        now = now_utc()
        if user["locked_until"] and user["locked_until"] > now:
            seconds = max(1, int((user["locked_until"] - now).total_seconds()))
            return jsonify(error="Too many failed attempts. Please wait before trying again.",
                           retryAfterSeconds=seconds, locked=True), 429

        cur.execute(
            "SELECT answer_hash FROM security_answers WHERE user_id=%s AND question_no=%s",
            (user["id"], question_no),
        )
        row = cur.fetchone()
        correct = bool(row) and bcrypt.checkpw(answer.lower().encode(), row["answer_hash"].encode())
        if not correct:
            log_event(cur, "SECURITY_ANSWER_FAILED", username_typed=identifier, user_id=user["id"],
                      details=f"Wrong security answer for Q{question_no}")
            attempts, _tier, seconds = apply_failed_login(cur, user, identifier)
            if seconds:
                return jsonify(error="Too many failed attempts. Please wait before trying again.",
                               retryAfterSeconds=seconds, locked=True, attempts=attempts), 429
            return json_error(GENERIC_ANSWER_ERROR, 401)

        clear_failures(cur, user["id"])
        code, _id, expires_at, retry_after = issue_otp(cur, user["id"], "reset")
        if not code:
            return jsonify(error="Please wait before requesting another code.",
                           retryAfterSeconds=retry_after), 429
        if not send_otp_email(user["email"], "reset", code, expires_at):
            return json_error("We could not send the reset email. Please try again.", 503)
        log_event(cur, "OTP_SENT", username_typed=identifier, user_id=user["id"],
                  details=f"Reset code emailed, expires {pht_string(expires_at)}")

    session["reset_user"] = str(user["id"])
    session["reset_identifier"] = identifier
    session["reset_at"] = now_utc().isoformat()
    session["reset_stage"] = "otp"
    return jsonify(otpRequired=True, message="Enter the 6-digit code we emailed you.",
                   expiresIn=RESET_TOKEN_MINUTES * 60, devMail=dev_mail_mode())


# ---------------------------------------------------------------------------
# Step 3: verify the reset OTP and issue a one-time reset token.
# ---------------------------------------------------------------------------
@bp.post("/api/forgot/otp")
def forgot_otp():
    retry = ip_throttled("forgot_otp", limit=20, window=300)
    if retry:
        return jsonify(error="Too many attempts. Please try again later.",
                       retryAfterSeconds=retry), 429

    user_id = _reset_session()
    if not user_id or session.get("reset_stage") != "otp":
        return json_error("Your reset session expired. Start again.", 401)

    code = re.sub(r"\s+", "", str((request.get_json(silent=True) or {}).get("code") or ""))
    if not re.fullmatch(r"\d{6}", code):
        return json_error("Enter the 6-digit code from your email.")

    with db() as conn, conn.cursor() as cur:
        ok, reason, remaining = verify_otp(cur, user_id, "reset", code)
        if not ok:
            record_otp_failure(cur, user_id, session.get("reset_identifier"))
            if reason == "expired":
                return json_error("That code has expired. Request a new one.", 401)
            if reason == "cancelled":
                return json_error("Too many incorrect codes. Request a new one.", 401)
            if reason == "missing":
                return json_error("No active code was found. Request a new one.", 401)
            return json_error(f"That code is not correct. {remaining} attempts left.", 401)

        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        cur.execute(
            """INSERT INTO password_reset_tokens(user_id, token_hash, expires_at, ip_address)
               VALUES (%s,%s, now() + (%s * interval '1 minute'), %s)""",
            (user_id, token_hash, RESET_TOKEN_MINUTES, client_ip()),
        )
        log_event(cur, "RESET_OTP_VERIFIED", username_typed=session.get("reset_identifier"),
                  user_id=user_id, details="Reset code accepted; one-time token issued")

    session["reset_stage"] = "token"
    session.pop("reset_user", None)
    session.pop("reset_at", None)
    return jsonify(
        message="Code accepted. Choose a new password.",
        resetUrl=f"/reset-password.html?token={token}",
        expiresIn=RESET_TOKEN_MINUTES * 60,
    )


@bp.post("/api/forgot/resend")
def forgot_resend():
    user_id = _reset_session()
    if not user_id or session.get("reset_stage") != "otp":
        return json_error("Your reset session expired. Start again.", 401)
    with db() as conn, conn.cursor() as cur:
        cur.execute("SELECT email,username FROM users WHERE id=%s", (user_id,))
        user = cur.fetchone()
        if not user:
            return json_error("Account not found.", 404)
        code, _id, expires_at, retry_after = issue_otp(cur, user_id, "reset")
        if not code:
            return jsonify(error="Please wait before requesting another code.",
                           retryAfterSeconds=retry_after), 429
        if not send_otp_email(user["email"], "reset", code, expires_at):
            return json_error("We could not send the email. Please try again.", 503)
        log_event(cur, "OTP_SENT", username_typed=user["username"], user_id=user_id,
                  details=f"Reset code resent, expires {pht_string(expires_at)}")
    return jsonify(message="A new reset code was sent.", expiresIn=RESET_TOKEN_MINUTES * 60,
                   devMail=dev_mail_mode())


# ---------------------------------------------------------------------------
# Step 4: validate the token and set the new password.
# ---------------------------------------------------------------------------
def _token_row(cur, token):
    token_hash = hashlib.sha256((token or "").encode()).hexdigest()
    cur.execute(
        """SELECT t.id, t.user_id, t.expires_at, t.used_at, u.email, u.username
             FROM password_reset_tokens t JOIN users u ON u.id=t.user_id
            WHERE t.token_hash=%s""",
        (token_hash,),
    )
    return cur.fetchone()


@bp.get("/api/reset/validate")
def validate_token():
    token = request.args.get("token") or ""
    if not token:
        return json_error("This password reset link is invalid or has already been used.", 403)
    with db() as conn, conn.cursor() as cur:
        row = _token_row(cur, token)
    if not row or row["used_at"] or row["expires_at"] <= now_utc():
        return json_error("This password reset link is invalid or has already been used.", 403)
    return jsonify(valid=True, username=row["username"] or row["email"])


@bp.post("/api/reset-password")
def reset_password():
    retry = ip_throttled("reset_password", limit=10, window=300)
    if retry:
        return jsonify(error="Too many attempts. Please try again later.",
                       retryAfterSeconds=retry), 429

    data = request.get_json(silent=True) or {}
    token = data.get("token") or ""
    password = data.get("password") or ""
    confirm = data.get("confirmPassword") or ""

    if password != confirm:
        return json_error("Mismatch Password.")
    message = validate_password(password, confirm)
    if message:
        return json_error(message)
    if password_strength(password) == "Weak":
        return json_error("Password is too weak. Use uppercase, lowercase, numbers or symbols.")

    with db() as conn, conn.cursor() as cur:
        row = _token_row(cur, token)
        if not row or row["used_at"] or row["expires_at"] <= now_utc():
            return json_error("This password reset link is invalid or has already been used.", 403)
        if is_recent_password(cur, row["user_id"], password):
            return json_error("You cannot reuse a recent password.")

        new_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()
        cur.execute(
            """UPDATE users SET password_hash=%s, password_changed_at=now(),
                      session_version=session_version+1
                WHERE id=%s""",
            (new_hash, row["user_id"]),
        )
        cur.execute("UPDATE password_reset_tokens SET used_at=now() WHERE id=%s", (row["id"],))
        remember_password(cur, row["user_id"], new_hash)
        log_event(cur, "PASSWORD_CHANGED", username_typed=row["username"], user_id=row["user_id"],
                  details="Password reset via Forgot Password")
        sent = send_password_changed(row["email"], client_ip(),
                                     request.headers.get("User-Agent", ""))
        if sent:
            log_event(cur, "ALERT_EMAIL_SENT", username_typed=row["username"], user_id=row["user_id"],
                      details="Password changed notification emailed")

    session.pop("reset_stage", None)
    session.pop("reset_user", None)
    session.pop("reset_at", None)
    return jsonify(message="Successfully Change Password.")
