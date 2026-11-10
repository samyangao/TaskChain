"""Verification queue and verify API."""

from flask import Blueprint, jsonify, request
from app.db import db
from app.permissions import login_required, roles_required
from app.services.audit import audit
from app.services.collaboration import blocking_message, notify_task_watchers, refresh_dependencies
from app.services.custody_chain import append_chain_record
from app.services.notifications import notify, notify_roles
from app.services.tasks import TASK_SELECT, task_dict
from app.utils import _short, json_error, parse_uuid

bp = Blueprint("verification", __name__)


@bp.get("/api/verifications")
@login_required
def verifications(user):
    if user["role"] not in {"administrator","coordinator","verifier"}: return json_error("Verifier permission required.",403)
    with db() as conn, conn.cursor() as cur:
        cur.execute(TASK_SELECT + " WHERE t.status IN ('for_verification','verified') ORDER BY t.updated_at DESC")
        rows=cur.fetchall()
    return jsonify(tasks=[task_dict(r) for r in rows])


@bp.post("/api/tasks/<task_id>/verify")
@login_required
@roles_required("administrator","coordinator","verifier")
def verify(user, task_id):
    if not parse_uuid(task_id): return json_error("Invalid task id.", 400)
    data=request.get_json(silent=True) or {}; decision=(data.get("decision") or "").lower(); remarks=(data.get("remarks") or "").strip()
    if decision not in {"approve","reject"}: return json_error("Decision must be approve or reject.")
    if decision=="reject" and not remarks: return json_error("Remarks are required when rejecting a task.")
    with db() as conn, conn.cursor() as cur:
        cur.execute("SELECT id,task_code,status,created_by,assigned_to FROM tasks WHERE id=%s",(task_id,)); t=cur.fetchone()
        if not t: return json_error("Task not found.",404)
        # Only a task that is actually awaiting verification can be decided.
        if t["status"] != "for_verification":
            return json_error("Only tasks awaiting verification can be approved or rejected.", 409)
        if decision == "approve":
            block = blocking_message(cur, task_id)
            if block:
                return json_error(block, 409)
        status="completed" if decision=="approve" else "rejected"
        cur.execute("INSERT INTO task_verifications(task_id,verifier_id,decision,remarks) VALUES(%s,%s,%s,%s)",(task_id,user["id"],decision,remarks))
        cur.execute("UPDATE tasks SET status=%s WHERE id=%s",(status,task_id))
        code = t["task_code"]; approved = decision == "approve"
        notify(cur, t["created_by"], "Task completed" if approved else "Task rejected",
               f"{code} was approved and completed. Please confirm it or reopen the request." if approved else f"{code} was rejected: {_short(remarks)}",
               task_id, "verification", actor_id=user["id"])
        if t["assigned_to"] and t["assigned_to"] != t["created_by"]:
            notify(cur, t["assigned_to"], "Task approved" if approved else "Task requires correction",
                   f"{code} was approved." if approved else f"{code} was rejected and needs correction: {_short(remarks)}",
                   task_id, "verification", actor_id=user["id"])
        if not approved:
            notify_roles(cur, ("administrator", "coordinator"), "Verification rejected",
                         f"{code} was rejected by {user['full_name']}: {_short(remarks)}", task_id, "verification", actor_id=user["id"])
        audit(cur,user["id"],f"task_{decision}d","task",task_id,remarks or "Completion approved")
        append_chain_record(cur, task_id, f"task_{decision}d", user["id"], {"decision": decision, "remarks": remarks, "new_status": status})
        notify_task_watchers(cur, task_id, "Verification recorded",
                             f"{code} was {'approved' if approved else 'rejected'} by {user['full_name']}.",
                             user["id"], "verification", exclude={t["created_by"], t["assigned_to"]})
        refresh_dependencies(cur, task_id, user["id"])
    return jsonify(message="Verification recorded.")
