"""Structured handover API (Phase 5)."""

import os
from flask import Blueprint, jsonify
from app.config import HANDOVER_BLOCKED_STATUSES
from app.db import db
from app.permissions import is_manager, login_required
from app.services.assignment_rules import accept_assignment, assignment_options
from app.services.audit import audit
from app.services.collaboration import blocking_message
from app.services.custody_chain import append_chain_record
from app.services.handovers import _parse_payload_request, _store_upload, _validate_attachments, _validate_checklist
from app.services.notifications import notify
from app.utils import json_error, parse_uuid

bp = Blueprint("handovers", __name__)


@bp.post("/api/tasks/<task_id>/handover/acknowledge")
@login_required
def acknowledge_handover(user, task_id):
    if not parse_uuid(task_id): return json_error("Invalid task id.", 400)
    with db() as conn, conn.cursor() as cur:
        return accept_assignment(cur, user, task_id, require_handover=True)


@bp.get("/api/tasks/<task_id>/handover-recipients")
@login_required
def handover_recipients(user, task_id):
    """Who this task could be handed to (with workload and team fit). Same permission as handing over."""
    if not parse_uuid(task_id): return json_error("Invalid task id.", 400)
    with db() as conn, conn.cursor() as cur:
        cur.execute("SELECT id,task_code,status,assigned_to,category FROM tasks WHERE id=%s", (task_id,))
        task = cur.fetchone()
        if not task: return json_error("Task not found.", 404)
        if task["assigned_to"] != user["id"] and not is_manager(user):
            return json_error("Only the current assignee or a coordinator can hand over this task.", 403)
        result = assignment_options(cur, task)
    people = [{k: o[k] for k in ("id", "full_name", "role", "active_tasks", "compatibility", "note")} for o in result["options"]
              if o["note"] != "Current holder"]
    return jsonify(recipients=people, team=result["team"])


@bp.get("/api/handovers/pending")
@login_required
def pending_handovers(user):
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT h.id, h.task_id, h.created_at, h.reason, t.task_code, t.title, f.full_name AS from_name
               FROM task_handovers h JOIN tasks t ON t.id=h.task_id JOIN users f ON f.id=h.from_user_id
               WHERE h.to_user_id=%s AND h.outcome='pending' ORDER BY h.created_at""", (user["id"],))
        rows = cur.fetchall()
    return jsonify(handovers=[{**r, "id": str(r["id"]), "task_id": str(r["task_id"])} for r in rows])


@bp.post("/api/tasks/<task_id>/handover")
@login_required
def handover(user, task_id):
    if not parse_uuid(task_id): return json_error("Invalid task id.", 400)
    data, files, error = _parse_payload_request()
    if error: return json_error(error)
    to_user = data.get("toUser")
    reason = " ".join(str(data.get("reason") or "").split())
    notes = str(data.get("notes") or "").strip()
    blockers = str(data.get("blockers") or "").strip()
    if not to_user or not reason: return json_error("Recipient and handover reason are required.")
    if not parse_uuid(to_user): return json_error("Invalid recipient.", 400)
    if len(reason) > 255: return json_error("The reason can be at most 255 characters.")
    if len(notes) > 2000: return json_error("Notes can be at most 2000 characters.")
    if len(blockers) > 1000: return json_error("Blockers can be at most 1000 characters.")
    items, error = _validate_checklist(data.get("checklist"))
    if error: return json_error(error)
    if any(i["state"] == "blocked" for i in items) and not blockers:
        return json_error("A checklist item is BLOCKED: describe what is blocking the work.")
    prepared, error = _validate_attachments(files)
    if error: return json_error(error)
    saved_paths = []
    try:
        with db() as conn, conn.cursor() as cur:
            cur.execute("SELECT id,task_code,assigned_to,created_by,status FROM tasks WHERE id=%s FOR UPDATE",(task_id,)); task=cur.fetchone()
            cur.execute("SELECT id,full_name FROM users WHERE id=%s AND is_active=TRUE",(to_user,)); target=cur.fetchone()
            if not task or not target: return json_error("Task or recipient not found.",404)
            if task["assigned_to"] != user["id"] and user["role"] not in {"administrator","coordinator"}: return json_error("Only the current assignee or a coordinator can hand over this task.",403)
            # These checks run before any write, so a refused handover leaves no trace anywhere.
            if not task["assigned_to"]:
                return json_error("Assign this task to someone before handing it over.", 409)
            if task["status"] in HANDOVER_BLOCKED_STATUSES:
                return json_error(f"A task that is {task['status'].replace('_', ' ')} cannot be handed over.", 409)
            block = blocking_message(cur, task_id)
            if block:
                return json_error(block, 409)
            if target["id"] == task["assigned_to"]:
                return json_error("That person already holds this task. Choose a different recipient.", 409)
            if task["assigned_to"] == user["id"]:
                cur.execute("SELECT 1 FROM task_handovers WHERE task_id=%s AND to_user_id=%s AND outcome='pending'", (task_id, user["id"]))
                if cur.fetchone():
                    return json_error("Acknowledge or decline the handover you received before handing the task on.", 409)
            # The sender is whoever really holds custody (the previous holder while a handover is still
            # waiting for acknowledgment), otherwise the current assignee. Not necessarily the person clicking.
            cur.execute("SELECT holder_id FROM task_custody WHERE task_id=%s AND ended_at IS NULL", (task_id,))
            custodian = cur.fetchone()
            from_id = custodian["holder_id"] if custodian else task["assigned_to"]
            cur.execute("SELECT full_name FROM users WHERE id=%s", (from_id,)); from_user = cur.fetchone()
            cur.execute("UPDATE task_handovers SET outcome='superseded', resolved_at=now() WHERE task_id=%s AND outcome='pending'", (task_id,))
            cur.execute(
                "INSERT INTO task_handovers(task_id,from_user_id,to_user_id,reason,notes,blockers,outcome,initiated_by) "
                "VALUES (%s,%s,%s,%s,%s,%s,'pending',%s) RETURNING id", (task_id, from_id, target["id"], reason, notes, blockers, user["id"]))
            handover_id = cur.fetchone()["id"]
            for position, item in enumerate(items):
                cur.execute("INSERT INTO task_handover_items(handover_id,position,label,state) VALUES (%s,%s,%s,%s)",
                            (handover_id, position, item["label"], item["state"]))
            stored_files = []
            for upload, name, size in prepared:
                stored, path = _store_upload(upload, task["task_code"]); saved_paths.append(path)
                cur.execute("INSERT INTO task_handover_attachments(handover_id,uploaded_by,filename,file_url,size_bytes) VALUES (%s,%s,%s,%s,%s)",
                            (handover_id, user["id"], name, f"/uploads/{stored}", size))
                stored_files.append({"filename": name, "size_bytes": size})
            cur.execute("UPDATE tasks SET assigned_to=%s,status='handover',accepted_at=NULL WHERE id=%s",(target["id"],task_id))
            cur.execute("INSERT INTO task_assignment_history(task_id,event,from_user_id,to_user_id,actor_id,reason) VALUES (%s,'handed_over',%s,%s,%s,%s)",
                        (task_id, from_id, target["id"], user["id"], reason))
            code = task["task_code"]
            audit(cur,user["id"],"handover_created","task",task_id,f"From {from_user['full_name']} to {target['full_name']}; reason: {reason}")
            append_chain_record(cur, task_id, "handover_created", user["id"], {
                "handover_id": str(handover_id), "from_user": str(from_id), "from_name": from_user["full_name"],
                "to_user": str(target["id"]), "to_name": target["full_name"], "initiated_by": str(user["id"]),
                "reason": reason, "notes": notes, "blockers": blockers, "checklist": items, "attachments": stored_files,
            })
            notify(cur,target["id"],"Task handed over",f"{code} has been handed over to you. Review the checklist and acknowledge it.",task_id,"handover",actor_id=user["id"])
            if from_id not in (user["id"], target["id"]):
                notify(cur,from_id,"Task handed over",f"{code} was handed over to {target['full_name']}.",task_id,"handover",actor_id=user["id"])
    except Exception:
        for path in saved_paths:  # never leave files behind for a handover that was rolled back
            try: os.remove(path)
            except OSError: pass
        raise
    return jsonify(message=f"Handover sent. It takes effect when {target['full_name']} acknowledges it.", handoverId=str(handover_id))
