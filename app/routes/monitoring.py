"""Admin-only, read-only security monitoring dashboard API (handout section 13)."""

from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify, request

from app.db import db
from app.permissions import login_required
from app.services.activity import PHT, log_event, pht_string
from app.utils import client_ip, json_error

bp = Blueprint("monitoring", __name__)

ADMIN_ROLES = {"administrator"}


def _deny(cur, user, details="Non-admin tried to open the security dashboard"):
    log_event(cur, "ADMIN_ACCESS_DENIED", username_typed=user.get("username") or user["email"],
              user_id=user["id"], details=details)
    return json_error("Access denied.", 403)


@bp.post("/api/admin/security/viewed")
@login_required
def dashboard_viewed(user):
    if user["role"] not in ADMIN_ROLES:
        with db() as conn, conn.cursor() as cur:
            return _deny(cur, user)
    with db() as conn, conn.cursor() as cur:
        log_event(cur, "ADMIN_VIEWED_DASHBOARD", username_typed=user.get("username") or user["email"],
                  user_id=user["id"], details="Security monitoring dashboard opened")
    return jsonify(message="View recorded.")


@bp.get("/api/admin/security/summary")
@login_required
def dashboard_summary(user):
    if user["role"] not in ADMIN_ROLES:
        with db() as conn, conn.cursor() as cur:
            return _deny(cur, user)

    with db() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT
                 count(*) FILTER (WHERE event_type='LOGIN_SUCCESS') AS logins_success,
                 count(*) FILTER (WHERE event_type='LOGIN_FAILED') AS logins_failed,
                 count(*) FILTER (WHERE event_type='OTP_SENT') AS otp_sent,
                 count(*) FILTER (WHERE event_type='OTP_FAILED') AS otp_failed,
                 count(*) FILTER (WHERE event_type='ALERT_EMAIL_SENT') AS alerts_sent
               FROM activity_log
              WHERE created_at >= (
                    date_trunc('day', now() AT TIME ZONE 'Asia/Manila')
                    AT TIME ZONE 'Asia/Manila'
              )"""
        )
        today = cur.fetchone()

        cur.execute("SELECT count(*) AS n FROM users WHERE locked_until IS NOT NULL AND locked_until > now()")
        locked_accounts = int(cur.fetchone()["n"])

        cur.execute("SELECT count(*) AS n FROM ip_blocks WHERE blocked_until > now()")
        blocked_ips = int(cur.fetchone()["n"])

        cur.execute(
            """SELECT date_trunc('hour', created_at) AS hour, count(*) AS n
                 FROM activity_log
                WHERE event_type='LOGIN_FAILED'
                  AND created_at >= now() - interval '24 hours'
                GROUP BY 1 ORDER BY 1"""
        )
        hourly_rows = cur.fetchall()
        counts = {row["hour"].astimezone(PHT).strftime("%Y-%m-%d %H"): int(row["n"]) for row in hourly_rows}
        now = datetime.now(PHT)
        hourly = []
        for offset in range(23, -1, -1):
            moment = (now - timedelta(hours=offset)).replace(minute=0, second=0, microsecond=0)
            key = moment.strftime("%Y-%m-%d %H")
            hourly.append({"hour": moment.strftime("%H:00"), "count": counts.get(key, 0)})

        cur.execute(
            """SELECT host(ip_address) AS ip, count(*) AS failures
                 FROM activity_log
                WHERE event_type IN ('LOGIN_FAILED','SECURITY_ANSWER_FAILED')
                  AND ip_address IS NOT NULL
                  AND created_at >= now() - interval '24 hours'
                GROUP BY ip_address
                ORDER BY failures DESC
                LIMIT 5"""
        )
        top_ips = []
        for row in cur.fetchall():
            cur.execute(
                "SELECT ceil(extract(epoch FROM (blocked_until - now())))::int AS seconds "
                "FROM ip_blocks WHERE ip_address=%s AND blocked_until > now()",
                (row["ip"],),
            )
            block = cur.fetchone()
            top_ips.append({
                "ip": row["ip"],
                "failures": int(row["failures"]),
                "blocked": bool(block),
                "blockedForSeconds": int(block["seconds"]) if block else 0,
            })

        cur.execute(
            """SELECT id, pattern, target, severity, details, flag_date, created_at
                 FROM security_flags
                ORDER BY flag_date DESC, created_at DESC
                LIMIT 20"""
        )
        flags = [
            {
                **row,
                "id": str(row["id"]),
                "flag_date": row["flag_date"].isoformat(),
                "created_at": row["created_at"].isoformat(),
            }
            for row in cur.fetchall()
        ]

        where, params = [], []
        event_type = (request.args.get("eventType") or "").strip()
        username = (request.args.get("username") or "").strip()
        ip_address = (request.args.get("ip") or "").strip()
        date_from = (request.args.get("from") or "").strip()
        date_to = (request.args.get("to") or "").strip()
        if event_type:
            where.append("event_type=%s")
            params.append(event_type)
        if username:
            where.append("COALESCE(username_typed,'') ILIKE %s")
            params.append(f"%{username}%")
        if ip_address:
            where.append("host(ip_address) = %s")
            params.append(ip_address)
        for value, operator in ((date_from, ">="), (date_to, "<=")):
            if value:
                try:
                    datetime.fromisoformat(value)
                except ValueError:
                    continue
                where.append(f"created_at {operator} %s")
                params.append(value)

        sql = """SELECT id, event_type, username_typed, user_id, host(ip_address) AS ip_address,
                        user_agent, details, created_at
                   FROM activity_log"""
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY created_at DESC LIMIT 50"
        cur.execute(sql, params)
        events = [
            {
                **row,
                "id": str(row["id"]),
                "user_id": str(row["user_id"]) if row["user_id"] else None,
                "created_at": row["created_at"].isoformat(),
            }
            for row in cur.fetchall()
        ]

        cur.execute(
            "SELECT DISTINCT event_type FROM activity_log ORDER BY event_type"
        )
        event_types = [row["event_type"] for row in cur.fetchall()]

    return jsonify(
        generatedAt=pht_string(),
        cards={
            "loginsSuccess": int(today["logins_success"]),
            "loginsFailed": int(today["logins_failed"]),
            "accountsLocked": locked_accounts,
            "ipsBlocked": blocked_ips,
            "otpSent": int(today["otp_sent"]),
            "otpFailed": int(today["otp_failed"]),
            "alertsSent": int(today["alerts_sent"]),
        },
        hourly=hourly,
        topIps=top_ips,
        flags=flags,
        events=events,
        eventTypes=event_types,
    )
