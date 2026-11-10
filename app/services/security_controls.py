"""Lockout tiers, IP blocks, password history, CSRF and idle-session helpers."""

import hmac
import secrets
from datetime import timedelta

import bcrypt
from flask import session

from app.config import (
    IDLE_TIMEOUT_MINUTES,
    IP_BLOCK_MINUTES,
    IP_BLOCK_THRESHOLD,
    IP_BLOCK_WINDOW_MINUTES,
    LOCKOUT_TIERS,
)
from app.services.activity import (
    block_ip,
    ip_block_remaining,
    log_event,
    now_utc,
    pht_string,
    recent_failure_count,
    user_agent,
)
from app.services.mailer import send_security_alert
from app.utils import client_ip


# ---------------------------------------------------------------------------
# Progressive lockout (handout section 8.3)
# ---------------------------------------------------------------------------
def lockout_for(attempts: int):
    """Return (tier, seconds) only when a threshold is crossed.

    Failures 4 and 5 do not lock again: the counter must reach 6 for tier 2.
    After 9, every third failure re-applies tier 3.
    """
    thresholds = {threshold: (index, seconds) for index, (threshold, seconds) in enumerate(LOCKOUT_TIERS, start=1)}
    if attempts in thresholds:
        return thresholds[attempts]
    if attempts > LOCKOUT_TIERS[-1][0] and (attempts - LOCKOUT_TIERS[-1][0]) % 3 == 0:
        return len(LOCKOUT_TIERS), LOCKOUT_TIERS[-1][1]
    return 0, 0


def apply_failed_login(cur, user, username_typed: str):
    """Record a failure, move to the right lockout tier, and alert the owner."""
    attempts = int(user["failed_login_attempts"] or 0) + 1
    tier, seconds = lockout_for(attempts)
    previous_tier = int(user["lockout_tier"] or 0)
    effective_tier = max(previous_tier, tier)
    locked_until = now_utc() + timedelta(seconds=seconds) if seconds else None

    cur.execute(
        """UPDATE users
              SET failed_login_attempts=%s, lockout_tier=%s,
                  locked_until=%s, last_failed_at=now()
            WHERE id=%s""",
        (attempts, effective_tier, locked_until, user["id"]),
    )
    log_event(
        cur,
        "LOGIN_FAILED",
        username_typed=username_typed,
        user_id=user["id"],
        details=f"Failed login attempt {attempts}",
    )

    if tier and tier > previous_tier:
        log_event(
            cur,
            f"LOCKOUT_TIER_{tier}",
            username_typed=username_typed,
            user_id=user["id"],
            details=f"Account reached lockout tier {tier} after {attempts} failed attempts ({seconds}s)",
        )
        sent = send_security_alert(
            user["email"],
            "Failed sign-in attempts on your account",
            [
                f"Account: {user['email']}",
                f"Failed attempts: {attempts}",
                f"Time: {pht_string()}",
                f"IP address: {client_ip()}",
                f"Browser: {user_agent() or 'unknown'}",
                f"Lockout: {seconds} seconds",
            ],
        )
        if sent:
            log_event(
                cur,
                "ALERT_EMAIL_SENT",
                username_typed=username_typed,
                user_id=user["id"],
                details=f"Lockout tier {tier} alert emailed to the account owner",
            )

    _maybe_block_ip(cur, username_typed)
    return attempts, tier, seconds


def _maybe_block_ip(cur, username_typed: str):
    ip = client_ip()
    if ip_block_remaining(cur, ip):
        return
    failures = recent_failure_count(cur, ip, IP_BLOCK_WINDOW_MINUTES)
    if failures >= IP_BLOCK_THRESHOLD:
        block_ip(
            cur,
            ip,
            IP_BLOCK_MINUTES,
            f"{failures} failures across any account in {IP_BLOCK_WINDOW_MINUTES} minutes",
        )
        log_event(
            cur,
            "IP_BLOCKED",
            username_typed=username_typed,
            details=f"IP blocked for {IP_BLOCK_MINUTES} minutes after {failures} failures",
        )


def clear_failures(cur, user_id):
    cur.execute(
        """UPDATE users
              SET failed_login_attempts=0, lockout_tier=0, locked_until=NULL
            WHERE id=%s""",
        (user_id,),
    )


def record_unknown_failure(cur, username_typed: str):
    """A login for a username that does not exist (or is inactive)."""
    log_event(
        cur,
        "LOGIN_FAILED",
        username_typed=username_typed,
        details="Unknown username or inactive account",
    )
    _maybe_block_ip(cur, username_typed)


def record_otp_failure(cur, user_id, username_typed: str):
    """Wrong OTP / wrong security answer also feeds the IP threshold."""
    log_event(
        cur,
        "OTP_FAILED",
        username_typed=username_typed,
        user_id=user_id,
        details="Wrong or expired one-time code",
    )
    _maybe_block_ip(cur, username_typed)


# ---------------------------------------------------------------------------
# Password history (protection 7)
# ---------------------------------------------------------------------------
def is_recent_password(cur, user_id, password: str) -> bool:
    cur.execute(
        """SELECT password_hash FROM password_history
            WHERE user_id=%s ORDER BY created_at DESC LIMIT 3""",
        (user_id,),
    )
    hashes = [row["password_hash"] for row in cur.fetchall()]
    cur.execute("SELECT password_hash FROM users WHERE id=%s", (user_id,))
    row = cur.fetchone()
    if row:
        hashes.append(row["password_hash"])
    return any(bcrypt.checkpw(password.encode(), item.encode()) for item in hashes)


def remember_password(cur, user_id, password_hash: str):
    cur.execute(
        "INSERT INTO password_history(user_id, password_hash) VALUES (%s,%s)",
        (user_id, password_hash),
    )
    cur.execute(
        """DELETE FROM password_history
            WHERE user_id=%s AND id NOT IN (
                SELECT id FROM password_history
                 WHERE user_id=%s ORDER BY created_at DESC LIMIT 3)""",
        (user_id, user_id),
    )


# ---------------------------------------------------------------------------
# CSRF (protection 3)
# ---------------------------------------------------------------------------
def ensure_csrf_token() -> str:
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token


def csrf_valid(supplied: str | None) -> bool:
    expected = session.get("csrf_token")
    return bool(expected and supplied and hmac.compare_digest(str(expected), str(supplied)))


# ---------------------------------------------------------------------------
# Idle session timeout (handout section 8.4 / protection 6)
# ---------------------------------------------------------------------------
def touch_session(update: bool = True) -> bool:
    """Return False when the session just expired. Updates last_activity."""
    if not session.get("user_id"):
        return True
    last = session.get("last_activity")
    if last:
        try:
            started = now_utc().fromisoformat(last)
            if started.tzinfo is None:
                started = started.replace(tzinfo=now_utc().tzinfo)
        except (TypeError, ValueError):
            started = None
        if started and now_utc() - started > timedelta(minutes=IDLE_TIMEOUT_MINUTES):
            session.clear()
            return False
    if update:
        session["last_activity"] = now_utc().isoformat()
    return True


def session_remaining_seconds() -> int:
    last = session.get("last_activity")
    if not last or not session.get("user_id"):
        return 0
    try:
        started = now_utc().fromisoformat(last)
        if started.tzinfo is None:
            started = started.replace(tzinfo=now_utc().tzinfo)
    except (TypeError, ValueError):
        return 0
    remaining = IDLE_TIMEOUT_MINUTES * 60 - int((now_utc() - started).total_seconds())
    return max(0, remaining)
