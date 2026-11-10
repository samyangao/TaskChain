"""Append-only activity log and shared security helpers."""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from flask import has_request_context, request

from app.db import db
from app.utils import client_ip

import ipaddress

PHT = ZoneInfo("Asia/Manila")


def valid_ip(value):
    try:
        ipaddress.ip_address(str(value))
        return str(value)
    except (ValueError, TypeError):
        return None


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def pht_now() -> datetime:
    return datetime.now(PHT)


def pht_string(value: datetime | None = None) -> str:
    value = value or pht_now()
    return value.astimezone(PHT).strftime("%Y-%m-%d %H:%M:%S PHT")


def user_agent() -> str:
    if not has_request_context():
        return ""
    return (request.headers.get("User-Agent") or "")[:500]


def log_event(
    cur,
    event_type: str,
    username_typed: str | None = None,
    user_id=None,
    details: str | None = None,
    ip_address: str | None = None,
    agent: str | None = None,
):
    """Insert one activity_log row. Never updates or deletes an existing row."""
    if ip_address is None and has_request_context():
        ip_address = client_ip()
    ip_address = valid_ip(ip_address)
    if agent is None and has_request_context():
        agent = user_agent()
    cur.execute(
        """INSERT INTO activity_log
               (event_type, username_typed, user_id, ip_address, user_agent, details)
           VALUES (%s,%s,%s,%s,%s,%s)""",
        (event_type, (username_typed or "")[:200] or None, user_id, ip_address, agent, details),
    )


def recent_failure_count(cur, ip_address: str, minutes: int) -> int:
    """Failures from one IP across any account inside the window."""
    ip_address = valid_ip(ip_address)
    if not ip_address:
        return 0
    cur.execute(
        """SELECT count(*) AS n
             FROM activity_log
            WHERE ip_address = %s
              AND event_type IN ('LOGIN_FAILED', 'OTP_FAILED', 'CAPTCHA_FAILED', 'SECURITY_ANSWER_FAILED')
              AND created_at >= now() - (%s * interval '1 minute')""",
        (ip_address, minutes),
    )
    return int(cur.fetchone()["n"])


def ip_block_remaining(cur, ip_address: str) -> int:
    """Seconds left on an active IP block, or 0."""
    ip_address = valid_ip(ip_address)
    if not ip_address:
        return 0
    cur.execute(
        "SELECT ceil(extract(epoch FROM (blocked_until - now())))::int AS seconds "
        "FROM ip_blocks WHERE ip_address=%s AND blocked_until > now()",
        (ip_address,),
    )
    row = cur.fetchone()
    return max(0, int(row["seconds"])) if row else 0


def block_ip(cur, ip_address: str, minutes: int, reason: str):
    ip_address = valid_ip(ip_address)
    if not ip_address:
        return
    cur.execute(
        """INSERT INTO ip_blocks(ip_address, blocked_until, reason)
           VALUES (%s, now() + (%s * interval '1 minute'), %s)
           ON CONFLICT (ip_address) DO UPDATE
              SET blocked_until = EXCLUDED.blocked_until,
                  reason = EXCLUDED.reason,
                  created_at = now()""",
        (ip_address, minutes, reason[:255]),
    )
