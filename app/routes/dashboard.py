"""Dashboard summary API."""

from flask import Blueprint, jsonify
from app.db import db
from app.permissions import login_required
from app.services.sla_engine import sla_state

bp = Blueprint("dashboard", __name__)


@bp.get("/api/dashboard")
@login_required
def dashboard(user):
    with db() as conn, conn.cursor() as cur:
        if user["role"] in {"administrator", "coordinator"}:
            cur.execute("SELECT count(*) AS n FROM tasks"); total = cur.fetchone()["n"]
            cur.execute("SELECT status,count(*) AS n FROM tasks GROUP BY status"); status_rows = cur.fetchall()
            cur.execute("SELECT count(*) AS n FROM tasks WHERE COALESCE(sla_due_at,deadline) < now() AND status NOT IN ('completed','cancelled','verified')"); overdue = cur.fetchone()["n"]
            cur.execute("SELECT count(*) AS n FROM tasks WHERE status='for_verification'"); verification = cur.fetchone()["n"]
            scope = "all"
        else:
            cur.execute("SELECT count(*) AS n FROM tasks WHERE created_by=%s OR assigned_to=%s", (user["id"],user["id"])); total = cur.fetchone()["n"]
            cur.execute("SELECT status,count(*) AS n FROM tasks WHERE created_by=%s OR assigned_to=%s GROUP BY status", (user["id"],user["id"])); status_rows = cur.fetchall()
            cur.execute("SELECT count(*) AS n FROM tasks WHERE COALESCE(sla_due_at,deadline) < now() AND status NOT IN ('completed','cancelled','verified') AND (created_by=%s OR assigned_to=%s)", (user["id"],user["id"])); overdue = cur.fetchone()["n"]
            cur.execute("SELECT count(*) AS n FROM tasks WHERE status='for_verification' AND (created_by=%s OR assigned_to=%s)", (user["id"],user["id"])); verification = cur.fetchone()["n"]
            scope = "mine"
        cur.execute("""SELECT t.id,t.task_code,t.title,t.priority,t.status,t.deadline,t.updated_at,
                       t.sla_escalated_at,COALESCE(t.sla_due_at,t.deadline) AS due_at,
                       r.full_name AS requester,a.full_name AS assignee
                       FROM tasks t JOIN users r ON r.id=t.created_by
                       LEFT JOIN users a ON a.id=t.assigned_to
                       WHERE (%s='all' OR t.created_by=%s OR t.assigned_to=%s)
                       ORDER BY t.updated_at DESC LIMIT 8""", (scope,user["id"],user["id"]))
        recent = [dict(r, sla_state=sla_state(r)) for r in cur.fetchall()]
        cur.execute("SELECT id,title,message,created_at,is_read FROM notifications WHERE user_id=%s ORDER BY created_at DESC LIMIT 5", (user["id"],))
        notifications = cur.fetchall()
    counts = {r["status"]: r["n"] for r in status_rows}
    return jsonify(summary={"total":total,"new_requests":counts.get("submitted",0),"in_progress":counts.get("in_progress",0)+counts.get("accepted",0),"waiting":counts.get("waiting",0),"handover":counts.get("handover",0),"verification":verification,"completed":counts.get("completed",0),"overdue":overdue}, recent=recent, notifications=notifications)
