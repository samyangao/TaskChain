"""In-app notification creation (notify, notify_roles)."""

from flask import g, has_request_context


def notify(cur, user_id, title, message, task_id=None, kind="system", actor_id=None, outbox=None):
    """Create an in-app notification (same transaction as the action that caused it).

    The person who performed the action is never notified about it. External
    delivery (email / Teams / Slack) is queued and sent after the response.
    """
    if actor_id is not None and str(user_id) == str(actor_id):
        return None
    cur.execute(
        "INSERT INTO notifications(user_id,title,message,task_id,kind) VALUES (%s,%s,%s,%s,%s) RETURNING id",
        (user_id, title, message, task_id, kind),
    )
    notification_id = cur.fetchone()["id"]
    entry = {
        "id": notification_id, "user_id": user_id, "title": title,
        "message": message, "task_id": task_id, "kind": kind,
    }
    if has_request_context():
        g.setdefault("notify_outbox", []).append(entry)
    elif outbox is not None:  # background jobs (the SLA scheduler) pass their own list
        outbox.append(entry)
    return notification_id


def notify_roles(cur, roles, title, message, task_id=None, kind="system", actor_id=None, outbox=None):
    cur.execute("SELECT id FROM users WHERE role = ANY(%s) AND is_active=TRUE", (list(roles),))
    for row in cur.fetchall():
        notify(cur, row["id"], title, message, task_id, kind, actor_id, outbox)
