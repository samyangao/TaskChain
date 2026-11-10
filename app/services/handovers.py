"""Structured handover helpers: custody periods, checklists and attachment storage (Phase 5)."""

import json
import os
from datetime import datetime, timezone
from flask import request
from uuid import uuid4
from werkzeug.utils import secure_filename
from app.config import ALLOWED_UPLOAD_EXTENSIONS, CHECKLIST_STATES, HANDOVER_MAX_FILES, HANDOVER_MAX_FILE_BYTES, UPLOAD_DIR


def custody_close(cur, task_id, reason):
    """End the open custody period of a task, if any. Returns the holder it belonged to."""
    cur.execute("UPDATE task_custody SET ended_at=now(), end_reason=%s WHERE task_id=%s AND ended_at IS NULL RETURNING holder_id",
                (reason, task_id))
    row = cur.fetchone()
    return row["holder_id"] if row else None


def custody_open(cur, task_id, holder_id, reason):
    """Start custody for a holder. A task never has two open periods: any stale one is closed first."""
    custody_close(cur, task_id, "replaced")
    cur.execute("INSERT INTO task_custody(task_id, holder_id, started_at, start_reason) VALUES (%s,%s,now(),%s)",
                (task_id, holder_id, reason))


def custody_periods(cur, task_id):
    """Every custody period of a task with its duration, plus the total per person."""
    cur.execute(
        """SELECT c.id, c.holder_id, u.full_name AS holder_name, c.started_at, c.ended_at, c.start_reason, c.end_reason,
                  EXTRACT(EPOCH FROM (COALESCE(c.ended_at, now()) - c.started_at))::bigint AS seconds
           FROM task_custody c JOIN users u ON u.id = c.holder_id
           WHERE c.task_id=%s ORDER BY c.started_at, c.id""", (task_id,))
    periods = [{"id": str(r["id"]), "holder_id": str(r["holder_id"]), "holder_name": r["holder_name"],
                "started_at": r["started_at"], "ended_at": r["ended_at"], "start_reason": r["start_reason"],
                "end_reason": r["end_reason"], "seconds": int(r["seconds"]), "open": r["ended_at"] is None} for r in cur.fetchall()]
    totals = {}
    for p in periods:
        totals.setdefault(p["holder_name"], 0)
        totals[p["holder_name"]] += p["seconds"]
    return {"periods": periods, "totals": [{"holder_name": n, "seconds": sec} for n, sec in totals.items()]}


def load_handovers(cur, task_id):
    """All handovers of a task with their checklist and attachments, oldest first."""
    cur.execute(
        """SELECT h.id, h.from_user_id, h.to_user_id, h.reason, h.notes, h.blockers, h.outcome, h.created_at, h.resolved_at,
                  f.full_name AS from_name, t.full_name AS to_name, i.full_name AS initiated_by_name
           FROM task_handovers h
           JOIN users f ON f.id = h.from_user_id JOIN users t ON t.id = h.to_user_id
           LEFT JOIN users i ON i.id = h.initiated_by
           WHERE h.task_id=%s ORDER BY h.created_at, h.id""", (task_id,))
    rows = cur.fetchall()
    ids = [r["id"] for r in rows]
    items, attachments = {}, {}
    if ids:
        cur.execute("SELECT handover_id, label, state FROM task_handover_items WHERE handover_id = ANY(%s) ORDER BY handover_id, position", (ids,))
        for r in cur.fetchall():
            items.setdefault(r["handover_id"], []).append({"label": r["label"], "state": r["state"]})
        cur.execute("SELECT id, handover_id, filename, file_url, size_bytes FROM task_handover_attachments WHERE handover_id = ANY(%s) ORDER BY created_at, id", (ids,))
        for r in cur.fetchall():
            attachments.setdefault(r["handover_id"], []).append(
                {"id": str(r["id"]), "filename": r["filename"], "url": r["file_url"], "size_bytes": r["size_bytes"]})
    return [{
        "id": str(r["id"]), "from_user_id": str(r["from_user_id"]), "to_user_id": str(r["to_user_id"]),
        "from_name": r["from_name"], "to_name": r["to_name"], "initiated_by_name": r["initiated_by_name"],
        "reason": r["reason"], "notes": r["notes"], "blockers": r["blockers"], "outcome": r["outcome"],
        "created_at": r["created_at"], "resolved_at": r["resolved_at"],
        "items": items.get(r["id"], []), "attachments": attachments.get(r["id"], []),
    } for r in rows]


def _checklist_summary(items):
    return {state: sum(1 for i in items if i["state"] == state) for state in CHECKLIST_STATES}


def _parse_payload_request():
    """JSON body, or multipart with a 'payload' JSON field plus 'files'. Returns (data, files, error)."""
    if request.mimetype == "multipart/form-data":
        try:
            data = json.loads(request.form.get("payload") or "{}")
        except ValueError:
            return None, None, "The submitted data could not be read."
        files = [f for f in request.files.getlist("files") if f and f.filename]
    else:
        data, files = request.get_json(silent=True) or {}, []
    if not isinstance(data, dict):
        return None, None, "The submitted data could not be read."
    return data, files, None


def _validate_checklist(raw):
    if not isinstance(raw, list) or not 1 <= len(raw) <= 20:
        return None, "Add between 1 and 20 checklist items."
    items = []
    for entry in raw:
        if not isinstance(entry, dict):
            return None, "Each checklist item needs a label and a state."
        label = " ".join(str(entry.get("label") or "").split())
        if not label or len(label) > 160:
            return None, "Each checklist item needs a label of up to 160 characters."
        if entry.get("state") not in CHECKLIST_STATES:
            return None, "Each checklist item must be DONE, PENDING or BLOCKED."
        items.append({"label": label, "state": entry["state"]})
    return items, None


_FILE_SIGNATURES = {
    ".jpg": [b"\xff\xd8\xff"], ".jpeg": [b"\xff\xd8\xff"], ".png": [b"\x89PNG\r\n\x1a\n"],
    ".gif": [b"GIF87a", b"GIF89a"], ".pdf": [b"%PDF-"],
    ".docx": [b"PK\x03\x04"], ".xlsx": [b"PK\x03\x04"],               # Office Open XML files are zip archives
    ".doc": [b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"], ".xls": [b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"],  # legacy OLE files
}


def _content_matches_type(ext, head):
    """The first bytes of a file must fit its extension, so a renamed program or web page is refused."""
    if ext == ".webp":
        return head[:4] == b"RIFF" and head[8:12] == b"WEBP"
    if ext in (".txt", ".csv"):
        return b"\x00" not in head
    return any(head.startswith(sig) for sig in _FILE_SIGNATURES.get(ext, []))


def _store_upload(upload, task_code):
    """Save one validated upload under a server-chosen name and return (stored_name, path)."""
    name = secure_filename(upload.filename)
    stored = f"{task_code}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}_{uuid4().hex[:8]}_{name}"
    path = os.path.join(UPLOAD_DIR, stored)
    upload.save(path)
    return stored, path


def _validate_attachments(files):
    if len(files) > HANDOVER_MAX_FILES:
        return None, f"Attach at most {HANDOVER_MAX_FILES} files."
    prepared = []
    for f in files:
        name = secure_filename(f.filename)
        ext = os.path.splitext(name)[1].lower()
        if not name or ext not in ALLOWED_UPLOAD_EXTENSIONS:
            return None, f"Unsupported file type: {ext or 'unknown'}. Allowed: {', '.join(sorted(e.lstrip('.') for e in ALLOWED_UPLOAD_EXTENSIONS))}."
        f.stream.seek(0, os.SEEK_END); size = f.stream.tell(); f.stream.seek(0)
        if size == 0:
            return None, f"{name} is empty."
        if size > HANDOVER_MAX_FILE_BYTES:
            return None, f"{name} is larger than {HANDOVER_MAX_FILE_BYTES // (1024 * 1024)} MB."
        head = f.stream.read(8192); f.stream.seek(0)
        if not _content_matches_type(ext, head):
            return None, f"{name} does not look like a real {ext.lstrip('.').upper()} file."
        prepared.append((f, name, size))
    return prepared, None
