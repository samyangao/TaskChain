"""Collaboration helpers: watchers, dependencies and blockers (Phase 7)."""

from app.permissions import is_manager
from app.services.custody_chain import append_chain_record
from app.services.notifications import notify


DEPENDENCY_REQUIRED_STATES = {"for_verification", "completed"}


def can_edit_collaboration(user, task):
    """Managers, the requester and the current responsible person can edit collaboration data."""
    return is_manager(user) or user["id"] in {task["created_by"], task["assigned_to"]}


def dependency_met(required_state, status):
    if required_state == "completed":
        return status == "completed"
    return status in {"for_verification", "verified", "completed"}


def task_blockers(cur, task_id):
    """Every task this task depends on, with a computed 'met' flag."""
    cur.execute(
        """SELECT d.depends_on_id, d.required_state, d.released_at,
                  t.task_code, t.title, t.status
           FROM task_dependencies d JOIN tasks t ON t.id=d.depends_on_id
           WHERE d.task_id=%s ORDER BY t.task_code""",
        (task_id,),
    )
    rows = []
    for row in cur.fetchall():
        item = dict(row)
        item["depends_on_id"] = str(item["depends_on_id"])
        item["met"] = dependency_met(item["required_state"], item["status"])
        rows.append(item)
    return rows


def blocking_message(cur, task_id):
    blocked = [r for r in task_blockers(cur, task_id) if not r["met"]]
    if not blocked:
        return None
    labels = [
        f"{r['task_code']} ({'completed' if r['required_state'] == 'completed' else 'for verification or later'})"
        for r in blocked
    ]
    return "This task is blocked by " + ", ".join(labels) + "."


def notify_task_watchers(cur, task_id, title, message, actor_id=None, kind="watch", exclude=()):
    excluded = {str(value) for value in exclude if value}
    cur.execute("SELECT user_id FROM task_watchers WHERE task_id=%s", (task_id,))
    for row in cur.fetchall():
        if str(row["user_id"]) in excluded:
            continue
        notify(cur, row["user_id"], title, message, task_id, kind, actor_id)


def watch_task(cur, task_id, user_id, added_by=None):
    cur.execute(
        "INSERT INTO task_watchers(task_id,user_id,added_by) VALUES(%s,%s,%s) ON CONFLICT DO NOTHING",
        (task_id, user_id, added_by or user_id),
    )


def refresh_dependencies(cur, task_id, actor_id=None):
    """Release or re-block tasks that depend on this task after its status changed."""
    cur.execute("SELECT task_code,status FROM tasks WHERE id=%s", (task_id,))
    source = cur.fetchone()
    if not source:
        return
    cur.execute(
        """SELECT d.task_id, d.required_state, d.released_at, b.task_code, b.created_by, b.assigned_to
           FROM task_dependencies d JOIN tasks b ON b.id=d.task_id
           WHERE d.depends_on_id=%s""",
        (task_id,),
    )
    for dep in cur.fetchall():
        met = dependency_met(dep["required_state"], source["status"])
        if met and dep["released_at"] is None:
            cur.execute("UPDATE task_dependencies SET released_at=now() WHERE task_id=%s AND depends_on_id=%s",
                        (dep["task_id"], task_id))
            title = "Dependency cleared"
            message = f"{dep['task_code']} is no longer blocked by {source['task_code']} and can proceed."
            append_chain_record(cur, dep["task_id"], "dependency_released", actor_id, {
                "depends_on": source["task_code"], "required_state": dep["required_state"],
            })
        elif not met and dep["released_at"] is not None:
            cur.execute("UPDATE task_dependencies SET released_at=NULL WHERE task_id=%s AND depends_on_id=%s",
                        (dep["task_id"], task_id))
            title = "Dependency reopened"
            message = f"{dep['task_code']} is blocked again by {source['task_code']}."
            append_chain_record(cur, dep["task_id"], "dependency_blocked", actor_id, {
                "depends_on": source["task_code"], "required_state": dep["required_state"],
            })
        else:
            continue
        recipients = {dep["created_by"], dep["assigned_to"]}
        for recipient in recipients:
            if recipient:
                notify(cur, recipient, title, message, dep["task_id"], "dependency", actor_id=actor_id)
        notify_task_watchers(cur, dep["task_id"], title, message, actor_id, "dependency", exclude=recipients)
