"""IT 107 registration, email verification, two-step login and profile."""

import bcrypt
import psycopg
import re
from datetime import datetime, timedelta, timezone
from io import BytesIO

from flask import Blueprint, jsonify, request, send_file, session

from app.config import (
    AUTH_QUESTIONS,
    MAX_PASSWORD_LENGTH,
    MIN_PASSWORD_LENGTH,
    OTP_EXPIRY_MINUTES,
)
from app.db import db
from app.permissions import current_user, login_required
from app.services.activity import log_event, now_utc, pht_string
from app.services.auth_service import _finish_login
from app.services.captcha import check_captcha, new_captcha
from app.services.crypto import decrypt_field, encrypt_field
from app.services.mailer import dev_mail_mode, send_otp_email
from app.services.otp import issue_otp, verify_otp
from app.services.registration_rules import validate_registration, validate_username
from app.services.security_controls import (
    apply_failed_login,
    clear_failures,
    ip_block_remaining,
    record_otp_failure,
    record_unknown_failure,
    remember_password,
    session_remaining_seconds,
)
from app.utils import client_ip, ip_throttled, json_error, parse_uuid

bp = Blueprint("auth", __name__)

GENERIC_LOGIN_ERROR = "Invalid username or password."
GENERIC_LOCKED_ERROR = "Too many failed attempts. Please wait before trying again."


class _OtpThrottled(Exception):
    """Internal signal: roll back the transaction and ask the user to wait."""


def _clear_keep_csrf():
    token = session.get("csrf_token")
    session.clear()
    if token:
        session["csrf_token"] = token


def _user_payload(user):
    return {
        "id": str(user["id"]),
        "fullName": user["full_name"],
        "email": user["email"],
        "role": user["role"],
        "username": user.get("username"),
    }


# ---------------------------------------------------------------------------
# CAPTCHA and live username check
# ---------------------------------------------------------------------------
@bp.get("/api/captcha")
def captcha_image():
    response = send_file(BytesIO(new_captcha()), mimetype="image/png", max_age=0)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    return response


@bp.get("/api/username-available")
def username_available():
    retry = ip_throttled("username_check", limit=120, window=60)
    if retry:
        return jsonify(available=False, message="Too many checks. Please wait a moment."), 429
    username = (request.args.get("username") or "").strip()
    message = validate_username(username)
    if message:
        return jsonify(available=False, message=message), 200
    with db() as conn, conn.cursor() as cur:
        cur.execute("SELECT 1 FROM users WHERE username=%s", (username,))
        taken = cur.fetchone() is not None
    return jsonify(
        available=not taken,
        message="That username is already taken." if taken else "That username is available.",
    )


@bp.get("/api/security/questions")
def security_questions():
    return jsonify(questions=[{"number": n, "question": q} for n, q in AUTH_QUESTIONS])


@bp.get("/api/security/config")
def security_config():
    """Public seeded values the browser needs for validation and countdowns."""
    from app.config import (
        FORGOT_PASSWORD_AFTER, IDLE_TIMEOUT_MINUTES, IP_BLOCK_THRESHOLD,
        LOCKOUT_TIERS, MAX_NAME_LENGTH, MAX_USERNAME_LENGTH, MIN_PASSWORD_LENGTH,
        MIN_USERNAME_LENGTH, OTP_EXPIRY_MINUTES,
    )
    return jsonify(
        minUsername=MIN_USERNAME_LENGTH,
        maxUsername=MAX_USERNAME_LENGTH,
        minPassword=MIN_PASSWORD_LENGTH,
        maxName=MAX_NAME_LENGTH,
        forgotAfter=FORGOT_PASSWORD_AFTER,
        lockoutTiers=[{"attempts": a, "seconds": s} for a, s in LOCKOUT_TIERS],
        otpExpiryMinutes=OTP_EXPIRY_MINUTES,
        idleMinutes=IDLE_TIMEOUT_MINUTES,
        ipBlockThreshold=IP_BLOCK_THRESHOLD,
        questions=[{"number": n, "question": q} for n, q in AUTH_QUESTIONS],
    )


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------
@bp.post("/api/register")
def register():
    retry = ip_throttled("register", limit=10, window=300)
    if retry:
        return jsonify(error="Too many registration attempts. Please try again later.",
                       retryAfterSeconds=retry), 429

    data = request.get_json(silent=True) or {}

    # CAPTCHA is checked before anything is saved. Deleting the widget in the
    # browser tools therefore cannot bypass it.
    if not check_captcha(data.get("captcha")):
        with db() as conn, conn.cursor() as cur:
            log_event(cur, "CAPTCHA_FAILED", username_typed=data.get("username"),
                      details="Registration CAPTCHA was missing or wrong")
        return json_error("The CAPTCHA code is not correct. Please try again.", 400)

    errors, clean, honeypot = validate_registration(data)
    if honeypot:
        # Refuse silently: bots see the ordinary success message, humans never
        # filled the hidden field, and no account is created.
        return jsonify(message="Account created. Check your email for the verification code."), 201
    if errors:
        return jsonify(error="Please correct the highlighted fields.", errors=errors), 400

    with db() as conn, conn.cursor() as cur:
        cur.execute("SELECT 1 FROM security_profiles WHERE id_number=%s", (clean["idNumber"],))
        if cur.fetchone():
            errors["idNumber"] = "This ID Number is already registered."
        cur.execute("SELECT 1 FROM users WHERE email=%s", (clean["email"],))
        if cur.fetchone():
            errors["email"] = "This email is already registered."
        cur.execute("SELECT 1 FROM users WHERE username=%s", (clean["username"],))
        if cur.fetchone():
            errors["username"] = "This username is already taken."
    if errors:
        return jsonify(error="Please correct the highlighted fields.", errors=errors), 409

    password_hash = bcrypt.hashpw(clean["password"].encode(), bcrypt.gensalt(rounds=12)).decode()
    full_name = " ".join(
        part for part in (
            clean["firstName"], clean["middleName"], clean["familyName"], clean["nameExtension"]
        ) if part
    )

    try:
        with db() as conn, conn.cursor() as cur:
            contact_enc = encrypt_field(cur, clean["contactNumber"])
            cur.execute(
                """INSERT INTO users(full_name,email,password_hash,role,username,is_verified)
                   VALUES (%s,%s,%s,'requester',%s,FALSE) RETURNING id""",
                (full_name, clean["email"], password_hash, clean["username"]),
            )
            uid = cur.fetchone()["id"]

            cur.execute(
                """INSERT INTO security_profiles
                       (id_number,user_id,first_name,middle_name,family_name,name_extension,
                        birthdate,purok_street,barangay,municipality,province,country,zip_code,
                        office_unit,contact_number_enc,date_of_appointment,position_designation,
                        privacy_consent_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    clean["idNumber"], uid, clean["firstName"], clean["middleName"],
                    clean["familyName"], clean["nameExtension"], clean["birthdate"],
                    clean["purokStreet"], clean["barangay"], clean["municipality"],
                    clean["province"], clean["country"], clean["zipCode"], clean["officeUnit"],
                    contact_enc, clean["dateOfAppointment"], clean["positionDesignation"],
                    now_utc(),
                ),
            )
            for answer in clean["answers"]:
                cur.execute(
                    "INSERT INTO security_answers(user_id,question_no,answer_hash) VALUES (%s,%s,%s)",
                    (
                        uid,
                        answer["questionNo"],
                        bcrypt.hashpw(answer["answer"].encode(), bcrypt.gensalt(rounds=12)).decode(),
                    ),
                )
            remember_password(cur, uid, password_hash)
            log_event(cur, "REGISTERED", username_typed=clean["username"], user_id=uid,
                      details=f"Account saved for ID Number {clean['idNumber']}; awaiting email verification")

            code, _otp_id, expires_at, retry_after = issue_otp(cur, uid, "register")
            if not code:
                raise _OtpThrottled(retry_after)
            if not send_otp_email(clean["email"], "register", code, expires_at):
                raise RuntimeError("verification email could not be sent")
            log_event(cur, "OTP_SENT", username_typed=clean["username"], user_id=uid,
                      details=f"Registration code emailed, expires {pht_string(expires_at)}")
    except _OtpThrottled as exc:
        return jsonify(error="Please wait before requesting another code.",
                       retryAfterSeconds=int(exc.args[0]) if exc.args else 60), 429
    except psycopg.errors.UniqueViolation:
        return jsonify(error="That ID Number, email or username is already registered."), 409
    except RuntimeError:
        return jsonify(error="We could not send the verification email. Please try again or contact the administrator."), 503

    _clear_keep_csrf()
    session["pending_verify_user"] = str(uid)
    session["pending_verify_email"] = clean["email"]
    session["pending_verify_name"] = clean["username"]
    session["pending_verify_at"] = now_utc().isoformat()
    return jsonify(
        message="Account created. Check your email for the verification code.",
        verifyRequired=True,
        email=clean["email"],
        expiresIn=OTP_EXPIRY_MINUTES * 60,
        devMail=dev_mail_mode(),
    ), 201


def _pending_verify_user(max_minutes=15):
    pending = session.get("pending_verify_user")
    started = session.get("pending_verify_at")
    if not pending or not parse_uuid(pending) or not started:
        return None
    try:
        when = datetime.fromisoformat(started)
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None
    if now_utc() - when > timedelta(minutes=max_minutes):
        return None
    return pending


@bp.post("/api/register/verify")
def register_verify():
    pending = _pending_verify_user()
    if not pending:
        return json_error("Your verification session expired. Please sign in again.", 401)
    code = re.sub(r"\s+", "", str((request.get_json(silent=True) or {}).get("code") or ""))
    if not re.fullmatch(r"\d{6}", code):
        return json_error("Enter the 6-digit code from your email.")

    with db() as conn, conn.cursor() as cur:
        ok, reason, remaining = verify_otp(cur, pending, "register", code)
        if not ok:
            record_otp_failure(cur, pending, session.get("pending_verify_name"))
            if reason == "expired":
                return json_error("That code has expired. Request a new one.", 401)
            if reason == "cancelled":
                return json_error("Too many incorrect codes. Request a new one.", 401)
            if reason == "missing":
                return json_error("No active code was found. Request a new one.", 401)
            return json_error(f"That code is not correct. {remaining} attempts left.", 401)
        cur.execute("UPDATE users SET is_verified=TRUE WHERE id=%s", (pending,))
        clear_failures(cur, pending)
        log_event(cur, "ACCOUNT_VERIFIED", username_typed=session.get("pending_verify_name"),
                  user_id=pending, details="Registration code accepted")

    for key in ("pending_verify_user", "pending_verify_email", "pending_verify_name", "pending_verify_at"):
        session.pop(key, None)
    return jsonify(message="Account verified. You can sign in now.")


@bp.post("/api/register/resend")
def register_resend():
    pending = _pending_verify_user()
    if not pending:
        return json_error("Your verification session expired. Please sign in again.", 401)
    with db() as conn, conn.cursor() as cur:
        cur.execute("SELECT email,username FROM users WHERE id=%s", (pending,))
        user = cur.fetchone()
        if not user:
            return json_error("Account not found.", 404)
        code, _id, expires_at, retry_after = issue_otp(cur, pending, "register")
        if not code:
            return jsonify(error="Please wait before requesting another code.",
                           retryAfterSeconds=retry_after), 429
        if not send_otp_email(user["email"], "register", code, expires_at):
            return json_error("We could not send the email. Please try again.", 503)
        log_event(cur, "OTP_SENT", username_typed=user["username"], user_id=pending,
                  details=f"Registration code resent, expires {pht_string(expires_at)}")
    return jsonify(message="A new verification code was sent.", expiresIn=OTP_EXPIRY_MINUTES * 60,
                   devMail=dev_mail_mode())


# ---------------------------------------------------------------------------
# Login: password step then email-OTP step
# ---------------------------------------------------------------------------
@bp.post("/api/login")
def login():
    retry = ip_throttled("login", limit=40, window=300)
    if retry:
        return jsonify(error="Too many login attempts from this address. Please try again later.",
                       retryAfterSeconds=retry), 429

    data = request.get_json(silent=True) or {}
    identifier = (data.get("identifier") or data.get("email") or "").strip()
    password = data.get("password") or ""
    remember = bool(data.get("remember"))
    if not check_captcha(data.get("captcha")):
        with db() as conn, conn.cursor() as cur:
            log_event(cur, "CAPTCHA_FAILED", username_typed=identifier,
                      details="Login CAPTCHA was missing or wrong")
        return json_error("The CAPTCHA code is not correct. Please try again.", 400)
    if not identifier or not password:
        return json_error(GENERIC_LOGIN_ERROR, 401)
    # Apply the seeded username shape and maximum password length. The message
    # stays generic so a malformed identifier cannot be distinguished from a
    # real account with a wrong password.
    if "@" not in identifier and validate_username(identifier):
        return json_error(GENERIC_LOGIN_ERROR, 401)
    if not MIN_PASSWORD_LENGTH <= len(password) <= MAX_PASSWORD_LENGTH:
        return json_error(GENERIC_LOGIN_ERROR, 401)

    with db() as conn, conn.cursor() as cur:
        remaining = ip_block_remaining(cur, client_ip())
        if remaining:
            return jsonify(error="Too many failed attempts from this address. Please try again later.",
                           retryAfterSeconds=remaining, ipBlocked=True), 429

        cur.execute(
            """SELECT id,full_name,email,username,password_hash,failed_login_attempts,
                      locked_until,lockout_tier,is_active,is_verified,role,session_version,totp_enabled
                 FROM users WHERE username=%s OR email=%s LIMIT 1""",
            (identifier, identifier),
        )
        user = cur.fetchone()
        if not user or not user["is_active"]:
            cur.execute("INSERT INTO login_attempts(email,success,ip_address) VALUES(%s,%s,%s)",
                        (identifier, False, client_ip()))
            record_unknown_failure(cur, identifier)
            return json_error(GENERIC_LOGIN_ERROR, 401)

        now = now_utc()
        if user["locked_until"] and user["locked_until"] > now:
            seconds = max(1, int((user["locked_until"] - now).total_seconds()))
            return jsonify(error=GENERIC_LOCKED_ERROR, retryAfterSeconds=seconds, locked=True), 429

        if not bcrypt.checkpw(password.encode(), user["password_hash"].encode()):
            attempts, tier, seconds = apply_failed_login(cur, user, identifier)
            cur.execute("INSERT INTO login_attempts(email,success,ip_address) VALUES(%s,%s,%s)",
                        (user["email"], False, client_ip()))
            if seconds:
                return jsonify(error=GENERIC_LOCKED_ERROR, retryAfterSeconds=seconds,
                               locked=True, attempts=attempts), 429
            return json_error(GENERIC_LOGIN_ERROR, 401)

        if not user["is_verified"]:
            code, _id, expires_at, retry_after = issue_otp(cur, user["id"], "register")
            if not code:
                return jsonify(error="Please wait before requesting another code.",
                               retryAfterSeconds=retry_after), 429
            if not send_otp_email(user["email"], "register", code, expires_at):
                return json_error("We could not send the verification email. Please try again.", 503)
            log_event(cur, "OTP_SENT", username_typed=identifier, user_id=user["id"],
                      details=f"Verification code emailed, expires {pht_string(expires_at)}")
            _clear_keep_csrf()
            session["pending_verify_user"] = str(user["id"])
            session["pending_verify_email"] = user["email"]
            session["pending_verify_name"] = identifier
            session["pending_verify_at"] = now_utc().isoformat()
            return jsonify(verifyRequired=True, message="Your account is not verified. We sent a new code.",
                           email=user["email"], expiresIn=OTP_EXPIRY_MINUTES * 60,
                           devMail=dev_mail_mode())

        code, _id, expires_at, retry_after = issue_otp(cur, user["id"], "login")
        if not code:
            return jsonify(error="Please wait before requesting another code.",
                           retryAfterSeconds=retry_after), 429
        if not send_otp_email(user["email"], "login", code, expires_at):
            return json_error("We could not send the log-in code. Please try again.", 503)
        log_event(cur, "OTP_SENT", username_typed=identifier, user_id=user["id"],
                  details=f"Login code emailed, expires {pht_string(expires_at)}")

    _clear_keep_csrf()
    session["pending_login_user"] = str(user["id"])
    session["pending_login_name"] = identifier
    session["pending_login_at"] = now_utc().isoformat()
    session["pending_login_remember"] = remember
    return jsonify(
        otpRequired=True,
        message="Enter the 6-digit code we emailed you.",
        email=user["email"],
        expiresIn=OTP_EXPIRY_MINUTES * 60,
        devMail=dev_mail_mode(),
    )


def _pending_login_user(max_minutes=15):
    pending = session.get("pending_login_user")
    started = session.get("pending_login_at")
    if not pending or not parse_uuid(pending) or not started:
        return None
    try:
        when = datetime.fromisoformat(started)
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None
    if now_utc() - when > timedelta(minutes=max_minutes):
        return None
    return pending


@bp.post("/api/login/otp")
def login_otp():
    retry = ip_throttled("login_totp", limit=30, window=300)
    if retry:
        return jsonify(error="Too many verification attempts. Please try again later.",
                       retryAfterSeconds=retry), 429

    pending = _pending_login_user()
    if not pending:
        _clear_keep_csrf()
        return json_error("Your sign-in session expired. Please enter your username and password again.", 401)

    code = re.sub(r"\s+", "", str((request.get_json(silent=True) or {}).get("code") or ""))
    if not re.fullmatch(r"\d{6}", code):
        return json_error("Enter the 6-digit code from your email.")

    with db() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT id,full_name,email,username,role,is_active,is_verified,
                      session_version,totp_enabled
                 FROM users WHERE id=%s""",
            (pending,),
        )
        user = cur.fetchone()
        if not user or not user["is_active"] or not user["is_verified"]:
            _clear_keep_csrf()
            return json_error("That account is not available. Please sign in again.", 401)

        ok, reason, remaining = verify_otp(cur, pending, "login", code)
        if not ok:
            record_otp_failure(cur, pending, session.get("pending_login_name"))
            if reason == "expired":
                return json_error("That code has expired. Request a new one.", 401)
            if reason == "cancelled":
                return json_error("Too many incorrect codes. Request a new one.", 401)
            if reason == "missing":
                return json_error("No active code was found. Request a new one.", 401)
            return json_error(f"That code is not correct. {remaining} attempts left.", 401)

        _finish_login(cur, user, bool(session.get("pending_login_remember")))

    return jsonify(message="Login successful.", user=_user_payload(user))


@bp.post("/api/login/resend")
def login_resend():
    pending = _pending_login_user()
    if not pending:
        return json_error("Your sign-in session expired. Please sign in again.", 401)
    with db() as conn, conn.cursor() as cur:
        cur.execute("SELECT email,username FROM users WHERE id=%s", (pending,))
        user = cur.fetchone()
        if not user:
            return json_error("Account not found.", 404)
        code, _id, expires_at, retry_after = issue_otp(cur, pending, "login")
        if not code:
            return jsonify(error="Please wait before requesting another code.",
                           retryAfterSeconds=retry_after), 429
        if not send_otp_email(user["email"], "login", code, expires_at):
            return json_error("We could not send the email. Please try again.", 503)
        log_event(cur, "OTP_SENT", username_typed=user["username"], user_id=pending,
                  details=f"Login code resent, expires {pht_string(expires_at)}")
    return jsonify(message="A new log-in code was sent.", expiresIn=OTP_EXPIRY_MINUTES * 60,
                   devMail=dev_mail_mode())


# ---------------------------------------------------------------------------
# Session, logout, profile
# ---------------------------------------------------------------------------
@bp.post("/api/logout")
@login_required
def logout(user):
    session.clear()
    return jsonify(message="Logged out.")


@bp.get("/api/session/status")
@login_required
def session_status(user):
    remaining = session_remaining_seconds()
    return jsonify(remainingSeconds=remaining, idleMinutes=remaining // 60,
                   warning=remaining <= 60)


@bp.get("/api/me")
@login_required
def me(user):
    profile = None
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT id_number,first_name,middle_name,family_name,name_extension,birthdate,
                      purok_street,barangay,municipality,province,country,zip_code,
                      office_unit,contact_number_enc,date_of_appointment,position_designation,
                      privacy_consent_at
                 FROM security_profiles WHERE user_id=%s""",
            (user["id"],),
        )
        row = cur.fetchone()
        if row:
            profile = {key: value for key, value in row.items() if key != "contact_number_enc"}
            try:
                profile["contact_number"] = decrypt_field(cur, row["contact_number_enc"])
            except Exception:
                profile["contact_number"] = None
            for key in ("birthdate", "date_of_appointment"):
                if profile.get(key):
                    profile[key] = profile[key].isoformat()
            if profile.get("privacy_consent_at"):
                profile["privacy_consent_at"] = profile["privacy_consent_at"].isoformat()

    return jsonify(user={
        **user,
        "id": str(user["id"]),
        "username": user.get("username"),
        "is_verified": user.get("is_verified"),
        "profile": profile,
        "password_changed_at": user["password_changed_at"].isoformat() if user.get("password_changed_at") else None,
    })
