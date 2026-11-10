"""Reports, exports and audit-log API (Phase 8)."""

import csv
import io
from app.services.report_pdf import build_report_pdf
from datetime import datetime, timezone
from flask import Blueprint, Response, jsonify
from app.db import db
from app.permissions import login_required
from app.services.reports import _SafeCsvWriter, _report_data
from app.utils import json_error

bp = Blueprint("reports", __name__)


@bp.get("/api/reports")
@login_required
def reports(user):
    if user["role"] not in {"administrator","coordinator"}: return json_error("Coordinator permission required.",403)
    return jsonify(**_report_data(include_options=True))


@bp.get("/api/reports/export.csv")
@login_required
def export_report_csv(user):
    if user["role"] not in {"administrator","coordinator"}: return json_error("Coordinator permission required.",403)
    data = _report_data(include_tasks=True)
    summary = data["summary"]
    output = io.StringIO()
    output.write("\ufeff")  # Excel opens UTF-8 CSV correctly with the BOM
    writer = _SafeCsvWriter(csv.writer(output))
    writer.writerow(["TaskChain operations report"])
    writer.writerow(["Generated", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")])
    writer.writerow(["Prepared by", user["full_name"]])
    writer.writerow(["Filters", data["filters"]])
    writer.writerow([])
    writer.writerow(["Key metrics"])
    for label, key in [("Total tasks", "total"), ("Active", "active"), ("Completed", "completed"),
                       ("Overdue", "overdue"), ("Historical (cancelled)", "historical"),
                       ("Reopened", "reopened"), ("Average resolution", "avg_resolution"),
                       ("SLA compliance", "sla_compliance")]:
        writer.writerow([label, summary.get(key)])
    writer.writerow([])
    writer.writerow(["Workload by person"])
    writer.writerow(["Person", "Active", "Completed", "Overdue", "Historical", "Total"])
    for person in data["workload"]:
        writer.writerow([person["full_name"], person["active"], person["completed"],
                         person["overdue"], person["historical"], person["total"]])
    writer.writerow([])
    writer.writerow(["Task register"])
    writer.writerow(["Task code", "Title", "Category", "Priority", "Status", "Requester",
                     "Responsible", "Created", "Due", "Completed"])
    for task in data["tasks"]:
        writer.writerow([
            task["task_code"], task["title"], task["category"], task["priority"], task["status"],
            task["requester"], task["assignee"] or "Unassigned", task["created_at"],
            task["due_at"], task["completed_at"],
        ])
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    return Response(
        output.getvalue().encode("utf-8"),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="taskchain-report-{stamp}.csv"'},
    )


@bp.get("/api/reports/export.pdf")
@login_required
def export_report_pdf(user):
    if user["role"] not in {"administrator","coordinator"}: return json_error("Coordinator permission required.",403)
    data = _report_data(include_tasks=True)
    report = {
        **data,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "generated_by": user["full_name"],
    }
    pdf = build_report_pdf(report)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    return Response(
        pdf,
        mimetype="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="taskchain-report-{stamp}.pdf"'},
    )


@bp.get("/api/audit-logs")
@login_required
def audit_logs(user):
    if user["role"] not in {"administrator","coordinator"}: return json_error("Administrator/coordinator permission required.",403)
    with db() as conn, conn.cursor() as cur:
        cur.execute("SELECT l.id,l.action,l.entity_type,l.entity_id,l.details,l.created_at,u.full_name AS actor_name FROM audit_logs l LEFT JOIN users u ON u.id=l.actor_id ORDER BY l.created_at DESC LIMIT 200")
        rows=cur.fetchall()
    return jsonify(logs=[{**r,"id":str(r["id"]),"entity_id":str(r["entity_id"]) if r["entity_id"] else None} for r in rows])
