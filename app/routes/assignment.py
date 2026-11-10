"""Assignment API: options, assign, reassign, accept, decline, escalate."""

from flask import Blueprint, jsonify, request
from app.config import HANDOVER_BLOCKED_STATUSES, SLA_STOPPED_STATUSES
from app.db import db
from app.permissions import login_required, roles_required
from app.services.assignment_rules import ACCEPTABLE_STATUSES, ASSIGNABLE_ROLES, _assign_task, _assignee_account, _clean_reason, _task_for_assignment, accept_assignment, assignment_options
from app.services.audit import audit
from app.services.custody_chain import append_chain_record
from app.services.handovers import custody_close
from app.services.notifications import notify, notify_roles
from app.utils import _short, json_error, parse_uuid

bp = Blueprint("assignment", __name__)


@bp.get("/api/tasks/<task_id>/assignment-options")
@login_required
@roles_required("administrator", "coordinator")
def get_assignment_options(user, task_id):
    if not parse_uuid(task_id): return json_error("Invalid task id.", 400)
    with db() as conn, conn.cursor() as cur:
        cur.execute("SELECT id,task_code,status,assigned_to,category FROM tasks WHERE id=%s", (task_id,))
        task = cur.fetchone()
        if not task: return json_error("Task not found.", 404)
        if task["status"] in HANDOVER_BLOCKED_STATUSES:
            return json_error(f"A task that is {task['status'].replace('_', ' ')} cannot be assigned.", 409)
        result = assignment_options(cur, task)
    return jsonify(task={"id": str(task["id"]), "task_code": task["task_code"], "category": task["category"],
                         "assigned_to": str(task["assigned_to"]) if task["assigned_to"] else None}, **result)


@bp.post("/api/tasks/<task_id>/assign")
@login_required
@roles_required("administrator", "coordinator")
def assign_task(user, task_id):
    if not parse_uuid(task_id): return json_error("Invalid task id.", 400)
    data = request.get_json(silent=True) or {}
    assignee = data.get("assignedTo")
    if not parse_uuid(assignee): return json_error("Select who to assign this task to.", 400)
    with db() as conn, conn.cursor() as cur:
        task = _task_for_assignment(cur, task_id); target = _assignee_account(cur, assignee)
        if not task or not target: return json_error("Task or user not found.", 404)
        if task["status"] in HANDOVER_BLOCKED_STATUSES:
            return json_error(f"A task that is {task['status'].replace('_', ' ')} cannot be assigned.", 409)
        if task["assigned_to"]:
            return json_error("This task is already assigned. Use Reassign to give it to someone else.", 409)
        if target["role"] not in ASSIGNABLE_ROLES:
            return json_error("That account cannot be assigned tasks.", 400)
        _assign_task(cur, user, task, target, "assigned")
    return jsonify(message="Task assigned.")


@bp.post("/api/tasks/<task_id>/reassign")
@login_required
@roles_required("administrator", "coordinator")
def reassign_task(user, task_id):
    if not parse_uuid(task_id): return json_error("Invalid task id.", 400)
    data = request.get_json(silent=True) or {}
    assignee = data.get("assignedTo")
    if not parse_uuid(assignee): return json_error("Select who to reassign this task to.", 400)
    reason = _clean_reason(data.get("reason"))
    if not reason: return json_error("Give a reason for the reassignment (up to 500 characters).", 400)
    with db() as conn, conn.cursor() as cur:
        task = _task_for_assignment(cur, task_id); target = _assignee_account(cur, assignee)
        if not task or not target: return json_error("Task or user not found.", 404)
        if task["status"] in HANDOVER_BLOCKED_STATUSES:
            return json_error(f"A task that is {task['status'].replace('_', ' ')} cannot be reassigned.", 409)
        if not task["assigned_to"]:
            return json_error("This task is not assigned yet. Use Assign.", 409)
        if task["assigned_to"] == target["id"]:
            return json_error("That person already holds this task. Choose someone else.", 409)
        if target["role"] not in ASSIGNABLE_ROLES:
            return json_error("That account cannot be assigned tasks.", 400)
        _assign_task(cur, user, task, target, "reassigned", reason)
    return jsonify(message="Task reassigned.")


@bp.post("/api/tasks/<task_id>/accept")
@login_required
def accept_task(user, task_id):
    if not parse_uuid(task_id): return json_error("Invalid task id.", 400)
    with db() as conn, conn.cursor() as cur:
        return accept_assignment(cur, user, task_id)


@bp.post("/api/tasks/<task_id>/decline")
@login_required
def decline_task(user, task_id):
    if not parse_uuid(task_id): return json_error("Invalid task id.", 400)
    data = request.get_json(silent=True) or {}
    reason = _clean_reason(data.get("reason"))
    if not reason: return json_error("Give a reason for declining (up to 500 characters).", 400)
    with db() as conn, conn.cursor() as cur:
        task = _task_for_assignment(cur, task_id)
        if not task: return json_error("Task not found.", 404)
        if task["assigned_to"] != user["id"]:
            return json_error("Only the person this task is assigned to can decline it.", 403)
        if task["accepted_at"] is not None or task["status"] not in ACCEPTABLE_STATUSES:
            return json_error("A task can only be declined before you accept it.", 409)
        cur.execute("SELECT id, from_user_id FROM task_handovers WHERE task_id=%s AND to_user_id=%s AND outcome='pending' "
                    "ORDER BY created_at DESC LIMIT 1 FOR UPDATE", (task["id"], user["id"]))
        declined_handover = cur.fetchone()
        if declined_handover:
            cur.execute("UPDATE task_handovers SET outcome='declined', resolved_at=now() WHERE id=%s", (declined_handover["id"],))
            if declined_handover["from_user_id"] != user["id"]:
                notify(cur, declined_handover["from_user_id"], "Handover declined",
                       f"{user['full_name']} declined the handover of {task['task_code']}: {_short(reason)}", task["id"], "handover", actor_id=user["id"])
        custody_close(cur, task["id"], "returned")  # nobody holds the task once it is back with the coordinators
        # Back to the coordinators as an unassigned request; the SLA clock keeps running.
        cur.execute("UPDATE tasks SET assigned_to=NULL, status='submitted', accepted_at=NULL WHERE id=%s", (task["id"],))
        cur.execute("INSERT INTO task_assignment_history(task_id,event,from_user_id,actor_id,reason) VALUES (%s,'declined',%s,%s,%s)",
                    (task["id"], user["id"], user["id"], reason))
        audit(cur, user["id"], "task_declined", "task", task["id"], f"Declined by {user['full_name']}: {reason}")
        append_chain_record(cur, task["id"], "task_declined", user["id"], {
            "declined_by": str(user["id"]), "declined_by_name": user["full_name"], "reason": reason, "from_status": task["status"],
            "handover_id": str(declined_handover["id"]) if declined_handover else None,
        })
        notify_roles(cur, ("administrator", "coordinator"), "Assignment declined",
                     f"{user['full_name']} declined {task['task_code']}: {_short(reason)}", task["id"], "assignment", actor_id=user["id"])
    return jsonify(message="You declined the task. It has gone back to the coordinators.")


@bp.post("/api/tasks/<task_id>/escalate")
@login_required
@roles_required("administrator", "coordinator")
def escalate_task(user, task_id):
    if not parse_uuid(task_id): return json_error("Invalid task id.", 400)
    data = request.get_json(silent=True) or {}
    reason = _clean_reason(data.get("reason"))
    if not reason: return json_error("Give a reason for escalating (up to 500 characters).", 400)
    with db() as conn, conn.cursor() as cur:
        task = _task_for_assignment(cur, task_id)
        if not task: return json_error("Task not found.", 404)
        if task["status"] in SLA_STOPPED_STATUSES:
            return json_error(f"A task that is {task['status']} cannot be escalated.", 409)
        cur.execute("INSERT INTO task_assignment_history(task_id,event,from_user_id,actor_id,reason) VALUES (%s,'escalated',%s,%s,%s)",
                    (task["id"], task["assigned_to"], user["id"], reason))
        audit(cur, user["id"], "task_escalated", "task", task["id"], f"Escalated by {user['full_name']}: {reason}")
        append_chain_record(cur, task["id"], "task_escalated", user["id"], {
            "manual": True, "escalated_by": str(user["id"]), "escalated_by_name": user["full_name"], "reason": reason,
        })
        notify_roles(cur, ("administrator",), "Task escalated",
                     f"{user['full_name']} escalated {task['task_code']}: {_short(reason)}", task["id"], "assignment", actor_id=user["id"])
    return jsonify(message="Task escalated to the administrators.")
