"""Custody chain API (Phase 1)."""

from datetime import datetime, timezone
from flask import Blueprint, jsonify
from app.db import db
from app.permissions import can_view_task, login_required, roles_required
from app.services.audit import audit
from app.services.custody_chain import verify_custody_chain
from app.services.handovers import custody_periods, load_handovers
from app.services.notifications import notify_roles
from app.services.tasks import TASK_SELECT, task_dict
from app.utils import json_error, parse_uuid

bp = Blueprint("custody", __name__)


@bp.get("/api/tasks/<task_id>/chain")
@login_required
def get_chain(user, task_id):
    if not parse_uuid(task_id):
        return json_error("Invalid task id.", 400)
    with db() as conn, conn.cursor() as cur:
        cur.execute(TASK_SELECT + " WHERE t.id=%s", (task_id,))
        task = cur.fetchone()
        if not task:
            return json_error("Task not found.", 404)
        if not can_view_task(user, task):
            return json_error("You do not have access to this task.", 403)
        cur.execute(
            """SELECT c.id, c.event_type, c.actor_id, c.event_data,
                      c.event_timestamp, c.sequence_number, c.previous_hash,
                      c.current_hash, u.full_name AS actor_name
               FROM custody_chain c
               LEFT JOIN users u ON u.id = c.actor_id
               WHERE c.task_id=%s
               ORDER BY c.sequence_number ASC""",
            (task_id,),
        )
        records = cur.fetchall()
    chain = [
        {
            "id": str(r["id"]),
            "event_type": r["event_type"],
            "actor_id": str(r["actor_id"]) if r["actor_id"] else None,
            "actor_name": r["actor_name"] or "System",
            "event_data": r["event_data"],
            "event_timestamp": r["event_timestamp"].isoformat() if hasattr(r["event_timestamp"], "isoformat") else str(r["event_timestamp"]),
            "sequence_number": r["sequence_number"],
            "previous_hash": r["previous_hash"],
            "current_hash": r["current_hash"],
        }
        for r in records
    ]
    return jsonify(chain=chain)


@bp.post("/api/tasks/<task_id>/chain/verify")
@login_required
@roles_required("administrator")
def verify_chain(user, task_id):
    if not parse_uuid(task_id):
        return json_error("Invalid task id.", 400)
    with db() as conn, conn.cursor() as cur:
        cur.execute("SELECT id, task_code FROM tasks WHERE id=%s", (task_id,))
        task = cur.fetchone()
        if not task:
            return json_error("Task not found.", 404)
        result = verify_custody_chain(task_id)
        if result["valid"]:
            audit(cur, user["id"], "chain_verified", "task", task_id,
                  f"Chain verification: VALID ({result['record_count']} records)")
        else:
            audit(cur, user["id"], "chain_verification_failed", "task", task_id,
                  f"Chain verification: INVALID at record #{result['broken_sequence']} - {result['reason']}")
            notify_roles(cur, ("administrator",), "Chain verification failed",
                         f"{task['task_code']}: custody chain is INVALID at record #{result['broken_sequence']}.",
                         task_id, "security", actor_id=user["id"])
    return jsonify(result)


@bp.get("/api/tasks/<task_id>/chain/report")
@login_required
@roles_required("administrator")
def chain_report(user, task_id):
    if not parse_uuid(task_id):
        return json_error("Invalid task id.", 400)
    with db() as conn, conn.cursor() as cur:
        cur.execute(TASK_SELECT + " WHERE t.id=%s", (task_id,))
        task = cur.fetchone()
        if not task:
            return json_error("Task not found.", 404)
        cur.execute(
            """SELECT c.id, c.event_type, c.actor_id, c.event_data,
                      c.event_timestamp, c.sequence_number, c.previous_hash,
                      c.current_hash, u.full_name AS actor_name, u.email AS actor_email
               FROM custody_chain c
               LEFT JOIN users u ON u.id = c.actor_id
               WHERE c.task_id=%s
               ORDER BY c.sequence_number ASC""",
            (task_id,),
        )
        records = cur.fetchall()
        handovers = load_handovers(cur, task_id)
        custody = custody_periods(cur, task_id)
    chain = [
        {
            "id": str(r["id"]),
            "event_type": r["event_type"],
            "actor_id": str(r["actor_id"]) if r["actor_id"] else None,
            "actor_name": r["actor_name"] or "System",
            "actor_email": r["actor_email"] or "—",
            "event_data": r["event_data"],
            "event_timestamp": r["event_timestamp"].isoformat() if hasattr(r["event_timestamp"], "isoformat") else str(r["event_timestamp"]),
            "sequence_number": r["sequence_number"],
            "previous_hash": r["previous_hash"],
            "current_hash": r["current_hash"],
        }
        for r in records
    ]
    report = {
        "task": task_dict(task),
        "requester": task["requester"],
        "requester_email": task["requester_email"],
        "current_status": task["status"],
        "chain": chain,
        "handovers": handovers,
        "custody": custody,
        "verification": verify_custody_chain(task_id),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generated_by": user["full_name"],
    }
    return jsonify(report=report)
