"""Task query/serialisation helpers (TASK_SELECT, task_dict)."""

from datetime import timedelta
from app.services.sla_engine import sla_state


TASK_SELECT = """SELECT t.id,t.task_code,t.title,t.description,t.category,t.priority,t.status,t.deadline,t.location,t.created_at,t.updated_at,
                         t.accepted_at,t.completed_at,t.confirmed_at,t.confirmation_type,t.reopen_count,t.sla_started_at,t.sla_due_at,t.sla_escalate_at,t.sla_warned_at,t.sla_overdue_at,t.sla_escalated_at,
                         COALESCE(t.sla_due_at,t.deadline) AS due_at,
                         t.created_by,t.assigned_to,r.full_name AS requester,r.email AS requester_email,
                         a.full_name AS assignee,a.email AS assignee_email,
                         (SELECT count(*) FROM task_subtasks s WHERE s.task_id=t.id) AS subtask_total,
                         (SELECT count(*) FROM task_subtasks s WHERE s.task_id=t.id AND s.is_done) AS subtask_done,
                         EXISTS (
                             SELECT 1 FROM task_dependencies d JOIN tasks dep ON dep.id=d.depends_on_id
                             WHERE d.task_id=t.id
                               AND NOT ((d.required_state='completed' AND dep.status='completed')
                                     OR (d.required_state='for_verification' AND dep.status IN ('for_verification','verified','completed')))
                         ) AS is_blocked
                  FROM tasks t JOIN users r ON r.id=t.created_by LEFT JOIN users a ON a.id=t.assigned_to"""


def completion_info(task, close_days):
    """Where a completed request stands with the requester: awaiting / confirmed / auto_closed / legacy."""
    if task["status"] != "completed":
        return {"state": None, "reopen_count": task["reopen_count"]}
    if task["confirmed_at"] is None:
        due = task["completed_at"] + timedelta(days=close_days) if (task["completed_at"] and close_days > 0) else None
        return {"state": "awaiting", "completed_at": task["completed_at"], "auto_close_at": due,
                "auto_close_days": close_days, "reopen_count": task["reopen_count"]}
    state = {"requester": "confirmed", "auto": "auto_closed"}.get(task["confirmation_type"], "legacy")
    return {"state": state, "completed_at": task["completed_at"], "confirmed_at": task["confirmed_at"],
            "rateable": state in ("confirmed", "auto_closed"), "reopen_count": task["reopen_count"]}


def task_dict(row):
    if not row: return None
    out = dict(row)
    out["id"] = str(out["id"])
    if out.get("created_by"): out["created_by"] = str(out["created_by"])
    if out.get("assigned_to"): out["assigned_to"] = str(out["assigned_to"])
    if "due_at" in out: out["sla_state"] = sla_state(out)
    return out
