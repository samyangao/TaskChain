"""Hashed, expiring, single-use one-time codes (handout section 6)."""

from datetime import timedelta

import bcrypt

from app.config import (
    OTP_EXPIRY_MINUTES,
    OTP_LENGTH,
    OTP_MAX_ATTEMPTS,
    OTP_MAX_RESENDS,
    OTP_RESEND_COOLDOWN_SECONDS,
    OTP_RESEND_WINDOW_MINUTES,
)
from app.services.activity import now_utc


def generate_code() -> str:
    """Cryptographically secure 6-digit code (never random.randrange)."""
    import secrets

    return f"{secrets.randbelow(10 ** OTP_LENGTH):0{OTP_LENGTH}d}"


def hash_code(code: str) -> str:
    return bcrypt.hashpw(str(code).encode(), bcrypt.gensalt(rounds=10)).decode()


def issue_otp(cur, user_id, purpose: str, ip_address=None):
    """Create a new OTP for user_id/purpose.

    Returns (code, otp_id, expires_at, retry_after). retry_after is non-zero
    when the 60-second cooldown or the 3-resends-per-15-minutes limit applies.
    """
    now = now_utc()
    cur.execute(
        """SELECT created_at FROM otp_codes
            WHERE user_id=%s AND purpose=%s
            ORDER BY created_at DESC LIMIT 1""",
        (user_id, purpose),
    )
    last = cur.fetchone()
    if last:
        elapsed = (now - last["created_at"]).total_seconds()
        if elapsed < OTP_RESEND_COOLDOWN_SECONDS:
            return None, None, None, int(OTP_RESEND_COOLDOWN_SECONDS - elapsed) + 1

    cur.execute(
        """SELECT count(*) AS n, min(created_at) AS first_at
             FROM otp_codes
            WHERE user_id=%s AND purpose=%s
              AND created_at >= now() - (%s * interval '1 minute')""",
        (user_id, purpose, OTP_RESEND_WINDOW_MINUTES),
    )
    window = cur.fetchone()
    if int(window["n"]) >= OTP_MAX_RESENDS + 1:
        oldest = window["first_at"]
        retry = OTP_RESEND_WINDOW_MINUTES * 60 - int((now - oldest).total_seconds())
        return None, None, None, max(1, retry)

    # Requesting a new code cancels every previous unconsumed code.
    cur.execute(
        """UPDATE otp_codes SET consumed_at=now()
            WHERE user_id=%s AND purpose=%s AND consumed_at IS NULL""",
        (user_id, purpose),
    )
    code = generate_code()
    expires_at = now + timedelta(minutes=OTP_EXPIRY_MINUTES)
    cur.execute(
        """INSERT INTO otp_codes(user_id, purpose, code_hash, expires_at, ip_address)
           VALUES (%s,%s,%s,%s,%s) RETURNING id""",
        (user_id, purpose, hash_code(code), expires_at, ip_address),
    )
    otp_id = cur.fetchone()["id"]
    return code, otp_id, expires_at, 0


def verify_otp(cur, user_id, purpose: str, code: str):
    """Check a code and spend it.

    Returns (ok, reason, remaining_attempts). Three wrong entries cancel the
    code, so even the correct code fails afterwards.
    """
    cur.execute(
        """SELECT id, code_hash, attempts, expires_at
             FROM otp_codes
            WHERE user_id=%s AND purpose=%s AND consumed_at IS NULL
            ORDER BY created_at DESC LIMIT 1""",
        (user_id, purpose),
    )
    row = cur.fetchone()
    if not row:
        return False, "missing", 0

    now = now_utc()
    if row["expires_at"] <= now:
        cur.execute("UPDATE otp_codes SET consumed_at=now() WHERE id=%s", (row["id"],))
        return False, "expired", 0
    if int(row["attempts"]) >= OTP_MAX_ATTEMPTS:
        cur.execute("UPDATE otp_codes SET consumed_at=now() WHERE id=%s", (row["id"],))
        return False, "cancelled", 0

    attempts = int(row["attempts"]) + 1
    if bcrypt.checkpw(str(code).encode(), row["code_hash"].encode()):
        cur.execute(
            "UPDATE otp_codes SET attempts=%s, consumed_at=now() WHERE id=%s",
            (attempts, row["id"]),
        )
        return True, "ok", 0

    if attempts >= OTP_MAX_ATTEMPTS:
        cur.execute(
            "UPDATE otp_codes SET attempts=%s, consumed_at=now() WHERE id=%s",
            (attempts, row["id"]),
        )
        return False, "cancelled", 0

    cur.execute("UPDATE otp_codes SET attempts=%s WHERE id=%s", (attempts, row["id"]))
    return False, "wrong", OTP_MAX_ATTEMPTS - attempts


def resend_state(cur, user_id, purpose: str):
    """Seconds until another resend is allowed, and resends left in the window."""
    cur.execute(
        """SELECT created_at FROM otp_codes
            WHERE user_id=%s AND purpose=%s
            ORDER BY created_at DESC LIMIT 1""",
        (user_id, purpose),
    )
    last = cur.fetchone()
    retry = 0
    if last:
        elapsed = (now_utc() - last["created_at"]).total_seconds()
        if elapsed < OTP_RESEND_COOLDOWN_SECONDS:
            retry = int(OTP_RESEND_COOLDOWN_SECONDS - elapsed) + 1

    cur.execute(
        """SELECT count(*) AS n FROM otp_codes
            WHERE user_id=%s AND purpose=%s
              AND created_at >= now() - (%s * interval '1 minute')""",
        (user_id, purpose, OTP_RESEND_WINDOW_MINUTES),
    )
    used = int(cur.fetchone()["n"])
    return retry, max(0, (OTP_MAX_RESENDS + 1) - used)
