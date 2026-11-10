"""Task evidence upload API."""

import os
from datetime import datetime, timezone
from flask import Blueprint, jsonify, request
from werkzeug.utils import secure_filename
from app.config import ALLOWED_UPLOAD_EXTENSIONS, UPLOAD_DIR
from app.db import db
from app.permissions import login_required
from app.services.audit import audit
from app.services.collaboration import blocking_message, notify_task_watchers, refresh_dependencies
from app.services.custody_chain import append_chain_record
from app.services.notifications import notify_roles
from app.utils import json_error, parse_uuid

bp = Blueprint("evidence", __name__)


@bp.post("/api/tasks/<task_id>/evidence")
@login_required
def evidence(user, task_id):
    if not parse_uuid(task_id): return json_error("Invalid task id.", 400)
    # Supports a real multipart file upload and a safe local file reference for testing.
    description = (request.form.get("description") or "").strip()
    if not description and request.is_json:
        description = (request.get_json(silent=True) or {}).get("description", "").strip()
    with db() as conn, conn.cursor() as cur:
        cur.execute("SELECT id,assigned_to,created_by,task_code,status FROM tasks WHERE id=%s",(task_id,)); t=cur.fetchone()
        if not t: return json_error("Task not found.",404)
        if user["role"] not in {"administrator","coordinator"} and user["id"] not in {t["assigned_to"],t["created_by"]}: return json_error("You do not have access to this task.",403)
        if t["assigned_to"] == user["id"] and t["status"] not in {"for_verification","verified","completed","cancelled"}:
            block = blocking_message(cur, task_id)
            if block:
                return json_error(block, 409)

        filename = None; file_url = None
        uploaded = request.files.get("file")
        if uploaded and uploaded.filename:
            filename = secure_filename(uploaded.filename)
            if not filename: return json_error("Invalid filename.")
            ext = os.path.splitext(filename)[1].lower()
            if ext not in ALLOWED_UPLOAD_EXTENSIONS: return json_error("Unsupported evidence file type.")
            stored = f"{t['task_code']}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}_{filename}"
            uploaded.save(os.path.join(UPLOAD_DIR, stored))
            file_url = f"/uploads/{stored}"
        elif request.is_json:
            data=request.get_json(silent=True) or {}
            filename=(data.get("filename") or "").strip(); file_url=(data.get("fileUrl") or "").strip(); description=(data.get("description") or "").strip()
            if not filename or not file_url: return json_error("Evidence file and description are required.")
        else:
            return json_error("Select an evidence file.")

        cur.execute("INSERT INTO task_evidence(task_id,uploaded_by,filename,file_url,description) VALUES(%s,%s,%s,%s,%s)",(task_id,user["id"],filename,file_url,description))
        cur.execute("UPDATE tasks SET status='for_verification' WHERE id=%s AND assigned_to=%s",(task_id,user["id"]))
        # Only when the task really moved to for_verification (the UPDATE above only matches
        # the assignee); evidence from anyone else must not tell verifiers it is ready.
        if cur.rowcount == 1:
            notify_roles(cur, ("verifier",), "Task ready for verification", f"{t['task_code']} has submitted evidence.", task_id, "verification", actor_id=user["id"])
            notify_task_watchers(cur, task_id, "Evidence submitted", f"{t['task_code']} is ready for verification.",
                                 user["id"], "verification", exclude={t["created_by"], t["assigned_to"]})
            refresh_dependencies(cur, task_id, user["id"])
        audit(cur,user["id"],"evidence_submitted","task",task_id,filename)
        append_chain_record(cur, task_id, "evidence_submitted", user["id"], {"filename": filename, "description": description})
    return jsonify(message="Evidence submitted.", fileUrl=file_url),201
