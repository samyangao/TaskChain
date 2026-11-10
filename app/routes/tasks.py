"""Task list, creation, detail and update API."""

import os
from flask import Blueprint, jsonify, request
from app.config import ALLOWED_TRANSITIONS, PRIORITIES, SLA_STOPPED_STATUSES, TASK_STATUSES
from app.db import db
from app.permissions import can_view_task, login_required
from app.services.assignment_rules import accept_assignment
from app.services.audit import audit
from app.services.collaboration import blocking_message, dependency_met, notify_task_watchers, refresh_dependencies
from app.services.custody_chain import append_chain_record
from app.services.handovers import _parse_payload_request, _store_upload, _validate_attachments, custody_periods, load_handovers
from app.services.notifications import notify, notify_roles
from app.services.sla_engine import apply_task_sla, find_category, get_auto_close_days
from app.services.tasks import TASK_SELECT, completion_info, task_dict
from app.utils import json_error, parse_uuid

bp = Blueprint("tasks", __name__)


@bp.get("/api/tasks")
@login_required
def tasks(user):
    status = request.args.get("status")
    q = (request.args.get("q") or "").strip()
    with db() as conn, conn.cursor() as cur:
        where, params = [], []
        if user["role"] not in {"administrator","coordinator"}:
            where.append("(t.created_by=%s OR t.assigned_to=%s)"); params += [user["id"],user["id"]]
        if status and status in TASK_STATUSES:
            where.append("t.status=%s"); params.append(status)
        if q:
            where.append("(t.task_code ILIKE %s OR t.title ILIKE %s OR r.full_name ILIKE %s OR COALESCE(a.full_name,'') ILIKE %s)")
            like=f"%{q}%"; params += [like,like,like,like]
        sql = TASK_SELECT + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY t.updated_at DESC"
        cur.execute(sql, params); rows=cur.fetchall()
    return jsonify(tasks=[task_dict(r) for r in rows])


@bp.post("/api/tasks")
@login_required
def create_task(user):
    data, files, error = _parse_payload_request()
    if error: return json_error(error)
    title=str(data.get("title") or "").strip(); description=str(data.get("description") or "").strip()
    category=str(data.get("category") or "General").strip(); priority=str(data.get("priority") or "medium").lower(); deadline=data.get("deadline") or None; location=str(data.get("location") or "").strip() or None
    if not title or len(title)>160: return json_error("Task title is required.")
    if priority not in PRIORITIES: return json_error("Invalid priority.")
    prepared, error = _validate_attachments(files)   # type, size and content are checked before anything is written
    if error: return json_error(error)
    saved_paths = []
    try:
        with db() as conn, conn.cursor() as cur:
            chosen = find_category(cur, category)
            if not chosen: return json_error("Choose a valid category.")
            category = chosen["name"]  # canonical spelling from the category table
            cur.execute("SELECT 'TC-' || lpad(nextval('task_code_seq')::text,6,'0') AS code")
            code=cur.fetchone()["code"]
            cur.execute("""INSERT INTO tasks(task_code,title,description,category,priority,status,deadline,location,created_by)
                           VALUES(%s,%s,%s,%s,%s,'submitted',%s,%s,%s) RETURNING id""",(code,title,description,category,priority,deadline,location,user["id"]))
            tid=cur.fetchone()["id"]
            stored_files = []
            for upload, name, size in prepared:
                stored, path = _store_upload(upload, code); saved_paths.append(path)
                cur.execute("INSERT INTO task_attachments(task_id,uploaded_by,filename,file_url,size_bytes) VALUES (%s,%s,%s,%s,%s)",
                            (tid, user["id"], name, f"/uploads/{stored}", size))
                stored_files.append({"filename": name, "size_bytes": size})
            sla = apply_task_sla(cur, tid)
            audit(cur,user["id"],"task_created","task",tid,f"Task {code} created" + (f" with {len(stored_files)} attachment(s)" if stored_files else ""))
            append_chain_record(cur, tid, "task_created", user["id"], {
                "task_code": code, "title": title, "category": category,
                "priority": priority, "deadline": deadline, "location": location,
                "sla_due_at": sla["due_at"].isoformat() if sla else None,
                "attachments": stored_files,
            })
            # Coordinators/admins receive the request.
            notify_roles(cur, ("administrator", "coordinator"), "New task request",
                         f"{user['full_name']} submitted {code}.", tid, "task", actor_id=user["id"])
    except Exception:
        for path in saved_paths:  # never leave files behind for a request that was rolled back
            try: os.remove(path)
            except OSError: pass
        raise
    return jsonify(message="Task created.", taskId=str(tid), taskCode=code, slaDueAt=sla["due_at"] if sla else None),201


@bp.get("/api/tasks/<task_id>")
@login_required
def get_task(user, task_id):
    if not parse_uuid(task_id):
        return json_error("Invalid task id.", 400)
    with db() as conn, conn.cursor() as cur:
        cur.execute(TASK_SELECT + " WHERE t.id=%s", (task_id,)); task=cur.fetchone()
        if not task: return json_error("Task not found.",404)
        if not can_view_task(user, task): return json_error("You do not have access to this task.",403)
        handovers = load_handovers(cur, task_id); custody = custody_periods(cur, task_id)
        cur.execute("""SELECT a.id, a.filename, a.file_url, a.size_bytes, a.created_at, u.full_name AS uploaded_by_name
                       FROM task_attachments a JOIN users u ON u.id=a.uploaded_by WHERE a.task_id=%s ORDER BY a.created_at, a.id""", (task_id,))
        attachments = [{"id": str(r["id"]), "filename": r["filename"], "url": r["file_url"], "size_bytes": r["size_bytes"],
                        "created_at": r["created_at"], "uploaded_by_name": r["uploaded_by_name"]} for r in cur.fetchall()]
        close_days = get_auto_close_days(cur)
        cur.execute("SELECT rating, comment, created_at FROM task_ratings WHERE task_id=%s AND cycle=%s", (task_id, task["reopen_count"]))
        rating = cur.fetchone()
        cur.execute("SELECT e.*,u.full_name AS uploader FROM task_evidence e JOIN users u ON u.id=e.uploaded_by WHERE e.task_id=%s ORDER BY e.created_at DESC", (task_id,)); evidence=cur.fetchall()
        cur.execute("SELECT v.*,u.full_name AS verifier_name FROM task_verifications v JOIN users u ON u.id=v.verifier_id WHERE v.task_id=%s ORDER BY v.created_at DESC", (task_id,)); verifications=cur.fetchall()
        cur.execute(
            """SELECT c.*, u.full_name AS author_name, u.role AS author_role,
                      COALESCE((SELECT array_agg(mu.full_name ORDER BY lower(mu.full_name))
                                FROM task_comment_mentions m JOIN users mu ON mu.id=m.user_id
                                WHERE m.comment_id=c.id), ARRAY[]::text[]) AS mention_names,
                      COALESCE((SELECT array_agg(m.user_id::text)
                                FROM task_comment_mentions m WHERE m.comment_id=c.id), ARRAY[]::text[]) AS mention_ids
               FROM task_comments c JOIN users u ON u.id=c.author_id
               WHERE c.task_id=%s ORDER BY c.created_at""",
            (task_id,),
        ); comments=cur.fetchall()
        cur.execute("SELECT l.*,u.full_name AS actor_name FROM audit_logs l LEFT JOIN users u ON u.id=l.actor_id WHERE l.entity_type='task' AND l.entity_id=%s ORDER BY l.created_at", (task_id,)); activity=cur.fetchall()
        cur.execute("""SELECT c.id,c.event_type,c.actor_id,c.event_data,c.event_timestamp,c.sequence_number,c.previous_hash,c.current_hash,u.full_name AS actor_name
                       FROM custody_chain c LEFT JOIN users u ON u.id=c.actor_id
                       WHERE c.task_id=%s ORDER BY c.sequence_number ASC""", (task_id,)); chain=cur.fetchall()
        cur.execute("""SELECT h.id,h.event,h.reason,h.created_at,f.full_name AS from_name,t.full_name AS to_name,a.full_name AS actor_name
                       FROM task_assignment_history h
                       LEFT JOIN users f ON f.id=h.from_user_id LEFT JOIN users t ON t.id=h.to_user_id
                       JOIN users a ON a.id=h.actor_id
                       WHERE h.task_id=%s ORDER BY h.created_at""", (task_id,)); assignment_history=cur.fetchall()
        cur.execute(
            """SELECT w.user_id, w.created_at, u.full_name, u.role
               FROM task_watchers w JOIN users u ON u.id=w.user_id
               WHERE w.task_id=%s ORDER BY lower(u.full_name)""",
            (task_id,),
        ); watchers=cur.fetchall()
        cur.execute(
            """SELECT s.id,s.title,s.position,s.is_done,s.done_at,s.created_at,s.done_by,u.full_name AS done_by_name
               FROM task_subtasks s LEFT JOIN users u ON u.id=s.done_by
               WHERE s.task_id=%s ORDER BY s.position, s.created_at""",
            (task_id,),
        ); subtasks=cur.fetchall()
        cur.execute(
            """SELECT d.depends_on_id,d.required_state,d.created_at,d.released_at,
                      t.task_code,t.title,t.status
               FROM task_dependencies d JOIN tasks t ON t.id=d.depends_on_id
               WHERE d.task_id=%s ORDER BY t.task_code""",
            (task_id,),
        ); dependencies=cur.fetchall()
        cur.execute(
            """SELECT d.task_id,d.required_state,t.task_code,t.title,t.status
               FROM task_dependencies d JOIN tasks t ON t.id=d.task_id
               WHERE d.depends_on_id=%s ORDER BY t.task_code""",
            (task_id,),
        ); dependents=cur.fetchall()
        cur.execute(
            """SELECT u.id,u.full_name,u.role FROM users u
               WHERE u.is_active=TRUE AND (
                     u.role IN ('administrator','coordinator') OR u.id=%s OR u.id=%s
                     OR EXISTS (SELECT 1 FROM task_watchers w WHERE w.task_id=%s AND w.user_id=u.id))
               ORDER BY lower(u.full_name)""",
            (task["created_by"], task["assigned_to"], task_id),
        ); mentionable=cur.fetchall()
        cur.execute("SELECT EXISTS(SELECT 1 FROM task_watchers WHERE task_id=%s AND user_id=%s) AS watching",
                    (task_id, user["id"])); watching=cur.fetchone()["watching"]
    def normalize(rows):
        result=[]
        for r in rows:
            x=dict(r)
            for k,v in list(x.items()):
                if hasattr(v,'hex') and k.endswith('_id'): x[k]=str(v)
            result.append(x)
        return result
    for dep in dependencies:
        dep["met"] = dependency_met(dep["required_state"], dep["status"])
    return jsonify(
        task=task_dict(task),
        handovers=handovers,
        custody=custody,
        attachments=attachments,
        completion=completion_info(task, close_days),
        rating=rating,
        evidence=normalize(evidence),
        verifications=normalize(verifications),
        comments=normalize(comments),
        activity=normalize(activity),
        chain=normalize(chain),
        assignment_history=normalize(assignment_history),
        watchers=normalize(watchers),
        watching=bool(watching),
        subtasks=normalize(subtasks),
        dependencies=normalize(dependencies),
        dependents=normalize(dependents),
        mentionable=[{**r, "id": str(r["id"])} for r in mentionable],
        blocked=any(not d["met"] for d in dependencies),
    )


@bp.patch("/api/tasks/<task_id>")
@login_required
def update_task(user, task_id):
    if not parse_uuid(task_id):
        return json_error("Invalid task id.", 400)
    data=request.get_json(silent=True) or {}
    with db() as conn, conn.cursor() as cur:
        cur.execute("SELECT id,task_code,status,assigned_to,created_by,category FROM tasks WHERE id=%s",(task_id,)); task=cur.fetchone()
        if not task: return json_error("Task not found.",404)
        if data.get("status") == "accepted" and task["status"] != "accepted":
            # Accepting is an assignment action with its own rules (only the assignee, only once);
            # it must go through the same routine as POST /accept so history, audit and chain agree.
            return accept_assignment(cur, user, task_id)
        if data.get("status") == "handover" and task["status"] != "handover":
            # A status of "handover" without a recipient, checklist and acknowledgment would be meaningless.
            return json_error("Use the Hand over form to hand a task to someone: it records the checklist, blockers and notes.", 400)
        task_category_before = task["category"]
        allowed_fields={}
        if "status" in data and data["status"] in TASK_STATUSES: allowed_fields["status"]=data["status"]
        if "priority" in data and data["priority"] in PRIORITIES: allowed_fields["priority"]=data["priority"]
        if "deadline" in data: allowed_fields["deadline"]=data["deadline"] or None
        if "category" in data:
            chosen = find_category(cur, (data["category"] or "General").strip())
            if not chosen: return json_error("Choose a valid category.")
            allowed_fields["category"] = chosen["name"]
        if "description" in data: allowed_fields["description"]=(data["description"] or "").strip()
        if not allowed_fields: return json_error("No valid changes supplied.")
        if not can_view_task(user, task): return json_error("You do not have permission to update this task.",403)
        # Enforce the workflow: a status change must be a legal transition from
        # the current state, otherwise a participant could self-approve.
        new_status = allowed_fields.get("status")
        if new_status and new_status != task["status"]:
            if new_status not in ALLOWED_TRANSITIONS.get(task["status"], set()):
                return json_error(
                    f"A task cannot move from '{task['status']}' to '{new_status}'.", 409
                )
            # Only a verifier/coordinator/administrator may close a task.
            if new_status in {"completed", "verified"} and user["role"] not in {"administrator", "coordinator", "verifier"}:
                return json_error("Only a verifier can complete a task.", 403)
            # A dependency blocks starting/resuming work, submitting for review and closing.
            if new_status not in {"submitted", "under_review", "assigned", "cancelled", "rejected"}:
                block = blocking_message(cur, task_id)
                if block:
                    return json_error(block, 409)
        sets=[]; params=[]
        for k,v in allowed_fields.items(): sets.append(f"{k}=%s"); params.append(v)
        params.append(task_id)
        cur.execute(f"UPDATE tasks SET {','.join(sets)} WHERE id=%s",params)
        if "category" in allowed_fields and allowed_fields["category"] != task_category_before and task["status"] not in SLA_STOPPED_STATUSES:
            apply_task_sla(cur, task_id)  # a different category means a different SLA
        audit(cur,user["id"],"task_updated","task",task_id,"; ".join(f"{k}={v}" for k,v in allowed_fields.items()))
        if new_status and new_status != task["status"]:
            append_chain_record(cur, task_id, "status_changed", user["id"], {
                "from_status": task["status"], "to_status": new_status,
            })
            code = task["task_code"]
            if new_status == "for_verification":
                notify_roles(cur, ("verifier",), "Task ready for verification", f"{code} is ready for verification.", task_id, "verification", actor_id=user["id"])
            elif new_status == "completed":
                notify(cur, task["created_by"], "Task completed", f"{code} was completed. Please confirm it or reopen the request.", task_id, "task", actor_id=user["id"])
            elif new_status == "rejected":
                notify(cur, task["created_by"], "Task rejected", f"{code} was rejected.", task_id, "task", actor_id=user["id"])
                if task["assigned_to"] and task["assigned_to"] != task["created_by"]:
                    notify(cur, task["assigned_to"], "Task requires correction", f"{code} was rejected and needs correction.", task_id, "task", actor_id=user["id"])
            notify_task_watchers(
                cur, task_id, "Task status changed",
                f"{code} moved from {task['status'].replace('_',' ')} to {new_status.replace('_',' ')}.",
                user["id"], "task", exclude={task["created_by"], task["assigned_to"]},
            )
            refresh_dependencies(cur, task_id, user["id"])
    return jsonify(message="Task updated.")
