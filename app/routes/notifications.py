"""Notifications and notification preferences API."""

from flask import Blueprint, jsonify, request
from app.db import db
from app.permissions import login_required
from app.services.notification_delivery import external_channels
from app.utils import json_error, parse_uuid

bp = Blueprint("notifications", __name__)


def _notification_dict(r):
    return {
        "id": str(r["id"]),
        "title": r["title"],
        "message": r["message"],
        "task_id": str(r["task_id"]) if r["task_id"] else None,
        "task_code": r["task_code"],
        "kind": r["kind"],
        "is_read": r["is_read"],
        "created_at": r["created_at"],
    }


PREFERENCE_CHANNELS = ("email", "teams", "slack")


@bp.get("/api/notifications")
@login_required
def get_notifications(user):
    try:
        limit = min(max(int(request.args.get("limit", 100)), 1), 200)
    except ValueError:
        limit = 100
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT n.id, n.title, n.message, n.task_id, t.task_code, n.kind, n.is_read, n.created_at
               FROM notifications n
               LEFT JOIN tasks t ON t.id = n.task_id
               WHERE n.user_id=%s
               ORDER BY n.created_at DESC
               LIMIT %s""",
            (user["id"], limit),
        )
        rows = cur.fetchall()
        cur.execute("SELECT count(*) AS c FROM notifications WHERE user_id=%s AND is_read=FALSE", (user["id"],))
        unread = cur.fetchone()["c"]
    return jsonify(notifications=[_notification_dict(r) for r in rows], unread_count=unread)


@bp.get("/api/notifications/unread-count")
@login_required
def notifications_unread_count(user):
    """Cheap endpoint the browser polls. 'latest' changes whenever a new
    notification arrives, even if the unread total happens to stay the same."""
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT count(*) FILTER (WHERE is_read=FALSE) AS unread, max(created_at) AS latest "
            "FROM notifications WHERE user_id=%s",
            (user["id"],),
        )
        row = cur.fetchone()
    return jsonify(unread_count=row["unread"], latest=row["latest"].isoformat() if row["latest"] else None)


@bp.post("/api/notifications/<notification_id>/read")
@login_required
def mark_notification_read(user, notification_id):
    if not parse_uuid(notification_id):
        return json_error("Invalid notification id.", 400)
    with db() as conn, conn.cursor() as cur:
        # user_id is part of the WHERE clause: nobody can mark someone else's notification.
        cur.execute(
            "UPDATE notifications SET is_read=TRUE WHERE id=%s AND user_id=%s RETURNING id",
            (notification_id, user["id"]),
        )
        if not cur.fetchone():
            return json_error("Notification not found.", 404)
        cur.execute("SELECT count(*) AS c FROM notifications WHERE user_id=%s AND is_read=FALSE", (user["id"],))
        unread = cur.fetchone()["c"]
    return jsonify(message="Notification marked as read.", unread_count=unread)


@bp.post("/api/notifications/read")
@login_required
def mark_notifications_read(user):
    with db() as conn, conn.cursor() as cur:
        cur.execute("UPDATE notifications SET is_read=TRUE WHERE user_id=%s AND is_read=FALSE", (user["id"],))
    return jsonify(message="Notifications marked as read.", unread_count=0)


@bp.get("/api/notification-preferences")
@login_required
def get_notification_preferences(user):
    with db() as conn, conn.cursor() as cur:
        cur.execute("SELECT email, teams, slack FROM notification_preferences WHERE user_id=%s", (user["id"],))
        row = cur.fetchone() or {}
    prefs = {ch: bool(row.get(ch, False)) for ch in PREFERENCE_CHANNELS}
    return jsonify(preferences=prefs, available=external_channels(), email_address=user["email"])


@bp.put("/api/notification-preferences")
@login_required
def update_notification_preferences(user):
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return json_error("Send the preferences as a JSON object.")
    unknown = set(data) - set(PREFERENCE_CHANNELS)
    if unknown or not data:
        return json_error("Valid preference names are email, teams and slack.")
    available = external_channels()
    for channel, value in data.items():
        if not isinstance(value, bool):
            return json_error(f"{channel} must be true or false.")
        if value and not available[channel]:
            return json_error(f"{channel.capitalize()} delivery is not configured on this server.", 409)
    with db() as conn, conn.cursor() as cur:
        cur.execute("INSERT INTO notification_preferences(user_id) VALUES (%s) ON CONFLICT (user_id) DO NOTHING", (user["id"],))
        for channel, value in data.items():  # channel names are whitelisted above
            cur.execute(f"UPDATE notification_preferences SET {channel}=%s, updated_at=now() WHERE user_id=%s", (value, user["id"]))
        cur.execute("SELECT email, teams, slack FROM notification_preferences WHERE user_id=%s", (user["id"],))
        row = cur.fetchone()
    return jsonify(message="Preferences saved.", preferences={ch: row[ch] for ch in PREFERENCE_CHANNELS})
