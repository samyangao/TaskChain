"""Requester loop: confirm, reopen and rate (Phase 6)."""

from datetime import datetime, timezone
from flask import Blueprint, jsonify, request
from app.db import db
from app.permissions import login_required
from app.services.assignment_rules import _clean_reason
from app.services.audit import audit
from app.services.custody_chain import append_chain_record
from app.services.handovers import custody_close
from app.services.notifications import notify, notify_roles
from app.services.sla_engine import apply_task_sla
from app.utils import _short, json_error, parse_uuid

bp = Blueprint("requester", __name__)


def _task_for_requester(cur, task_id, user):
    """Lock the task and make sure the caller is the person who requested it. Returns (task, error_response)."""
    cur.execute("SELECT id,task_code,status,created_by,assigned_to,confirmed_at,confirmation_type,reopen_count "
                "FROM tasks WHERE id=%s FOR UPDATE", (task_id,))
    task = cur.fetchone()
    if not task: return None, json_error("Task not found.", 404)
    if task["created_by"] != user["id"]:
        return None, json_error("Only the person who requested this task can do that.", 403)
    return task, None


@bp.post("/api/tasks/<task_id>/confirm")
@login_required
def confirm_task(user, task_id):
    if not parse_uuid(task_id): return json_error("Invalid task id.", 400)
    with db() as conn, conn.cursor() as cur:
        task, err = _task_for_requester(cur, task_id, user)
        if err: return err
        if task["status"] != "completed":
            return json_error("This request has not been completed yet.", 409)
        if task["confirmed_at"] is not None:
            return json_error("This request is already closed.", 409)
        cur.execute("UPDATE tasks SET confirmed_at=now(), confirmation_type='requester' WHERE id=%s", (task["id"],))
        audit(cur, user["id"], "task_confirmed", "task", task["id"], f"Completion confirmed by {user['full_name']}")
        append_chain_record(cur, task["id"], "task_confirmed", user["id"], {
            "confirmed_by": str(user["id"]), "confirmed_by_name": user["full_name"], "reopen_count": task["reopen_count"],
        })
        if task["assigned_to"]:
            notify(cur, task["assigned_to"], "Completion confirmed", f"{user['full_name']} confirmed that {task['task_code']} is complete.",
                   task["id"], "task", actor_id=user["id"])
    return jsonify(message="Thank you. The request is closed. You can now rate it.")


@bp.post("/api/tasks/<task_id>/reopen")
@login_required
def reopen_task(user, task_id):
    if not parse_uuid(task_id): return json_error("Invalid task id.", 400)
    data = request.get_json(silent=True) or {}
    reason = _clean_reason(data.get("reason"))
    if not reason: return json_error("Give a reason for reopening the request (up to 500 characters).", 400)
    with db() as conn, conn.cursor() as cur:
        task, err = _task_for_requester(cur, task_id, user)
        if err: return err
        if task["status"] != "completed":
            return json_error("Only a completed request can be reopened.", 409)
        if task["confirmed_at"] is not None:
            return json_error("This request is already closed. Please submit a new request instead.", 409)
        holder = None
        if task["assigned_to"]:
            cur.execute("SELECT id FROM users WHERE id=%s AND is_active=TRUE", (task["assigned_to"],))
            holder = task["assigned_to"] if cur.fetchone() else None
        new_status = "assigned" if holder else "submitted"  # back to the person who did it (who must accept again), else to the coordinators
        cur.execute("""UPDATE tasks SET status=%s, assigned_to=%s, accepted_at=NULL, completed_at=NULL,
                       reopen_count=reopen_count+1 WHERE id=%s""", (new_status, holder, task["id"]))
        custody_close(cur, task["id"], "reopened")
        apply_task_sla(cur, task["id"], start=datetime.now(timezone.utc))  # a reopened request gets a fresh SLA clock
        cur.execute("INSERT INTO task_assignment_history(task_id,event,to_user_id,actor_id,reason) VALUES (%s,'reopened',%s,%s,%s)",
                    (task["id"], holder, user["id"], reason))
        audit(cur, user["id"], "task_reopened", "task", task["id"], f"Reopened by {user['full_name']}: {reason}")
        append_chain_record(cur, task["id"], "task_reopened", user["id"], {
            "reopened_by": str(user["id"]), "reopened_by_name": user["full_name"], "reason": reason,
            "reopen_number": task["reopen_count"] + 1, "new_status": new_status, "assigned_to": str(holder) if holder else None,
        })
        msg = f"{user['full_name']} reopened {task['task_code']}: {_short(reason)}"
        notify_roles(cur, ("administrator", "coordinator"), "Request reopened", msg, task["id"], "task", actor_id=user["id"])
        if holder and holder != user["id"]:
            cur.execute("SELECT role FROM users WHERE id=%s", (holder,))
            if cur.fetchone()["role"] not in ("administrator", "coordinator"):  # managers were just notified above
                notify(cur, holder, "Request reopened", msg, task["id"], "task", actor_id=user["id"])
    return jsonify(message="The request was reopened and sent back for more work.")


@bp.post("/api/tasks/<task_id>/rating")
@login_required
def rate_task(user, task_id):
    if not parse_uuid(task_id): return json_error("Invalid task id.", 400)
    data = request.get_json(silent=True) or {}
    rating, comment = data.get("rating"), data.get("comment")
    if not isinstance(rating, int) or isinstance(rating, bool) or not 1 <= rating <= 5:
        return json_error("Choose a rating from 1 to 5.", 400)
    comment = " ".join(str(comment or "").split()) if not isinstance(comment, (dict, list)) else None
    if comment is None or len(comment) > 1000:
        return json_error("The comment can be at most 1000 characters.", 400)
    with db() as conn, conn.cursor() as cur:
        task, err = _task_for_requester(cur, task_id, user)
        if err: return err
        if task["status"] != "completed" or task["confirmation_type"] not in ("requester", "auto"):
            return json_error("You can rate a request after you have confirmed it, or after it was closed automatically.", 409)
        cur.execute("INSERT INTO task_ratings(task_id,rated_by,rating,comment,cycle) VALUES (%s,%s,%s,%s,%s) ON CONFLICT (task_id,cycle) DO NOTHING RETURNING id",
                    (task["id"], user["id"], rating, comment, task["reopen_count"]))
        if not cur.fetchone():
            return json_error("You have already rated this request.", 409)
        audit(cur, user["id"], "task_rated", "task", task["id"], f"Rated {rating}/5" + (f": {_short(comment)}" if comment else ""))
    return jsonify(message="Thank you for your feedback.")
