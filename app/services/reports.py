"""Report filters, data builders and safe CSV writer (Phase 8)."""

from datetime import datetime, timedelta, timezone
from flask import request
from app.config import PRIORITIES, TASK_STATUSES
from app.db import db
from app.utils import parse_uuid


REPORT_STATUSES = sorted(TASK_STATUSES)


def _report_date(value):
    try:
        return datetime.strptime(str(value or "").strip(), "%Y-%m-%d").date()
    except ValueError:
        return None


def _report_filters():
    """Translate report query parameters into a safe WHERE clause."""
    args = request.args
    where, params = [], []
    date_from = _report_date(args.get("from"))
    date_to = _report_date(args.get("to"))
    category = (args.get("category") or "").strip()
    status = (args.get("status") or "").strip().lower()
    priority = (args.get("priority") or "").strip().lower()
    assignee = (args.get("assignee") or "").strip()
    team = (args.get("team") or "").strip()
    q = (args.get("q") or "").strip()
    if date_from:
        where.append("t.created_at >= %s")
        params.append(datetime.combine(date_from, datetime.min.time(), tzinfo=timezone.utc))
    if date_to:
        where.append("t.created_at < %s")
        params.append(datetime.combine(date_to + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc))
    if category:
        where.append("t.category = %s")
        params.append(category)
    if status in TASK_STATUSES:
        where.append("t.status = %s")
        params.append(status)
    if priority in PRIORITIES:
        where.append("t.priority = %s")
        params.append(priority)
    if assignee and parse_uuid(assignee):
        where.append("t.assigned_to = %s")
        params.append(assignee)
    if team:
        where.append("EXISTS (SELECT 1 FROM user_teams ut WHERE ut.user_id=t.assigned_to AND lower(ut.team)=lower(%s))")
        params.append(team)
    if q:
        where.append("(t.task_code ILIKE %s OR t.title ILIKE %s)")
        like = f"%{q}%"
        params += [like, like]
    parts = []
    if date_from or date_to:
        parts.append(f"{date_from.isoformat() if date_from else 'start'} to {date_to.isoformat() if date_to else 'today'}")
    if category: parts.append(category)
    if status: parts.append(status.replace("_", " ").title())
    if priority: parts.append(priority.title())
    if assignee:
        parts.append("one assignee")
    if team: parts.append(f"team {team}")
    if q: parts.append(f'search "{q}"')
    description = "All tasks" if not parts else " · ".join(parts)
    return where, params, description


def _report_where_sql(where):
    return (" WHERE " + " AND ".join(where)) if where else ""


def _report_dt(value):
    if not value:
        return "—"
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d %H:%M")
    return str(value)


def _report_data(include_tasks=False, include_options=False):
    where, params, description = _report_filters()
    where_sql = _report_where_sql(where)
    due = "COALESCE(t.sla_due_at,t.deadline)"
    open_status = "t.status NOT IN ('completed','cancelled','verified')"
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            f"""SELECT count(*) AS total,
                       count(*) FILTER (WHERE {open_status}
                           AND ({due} IS NULL OR {due} >= now())) AS active,
                       count(*) FILTER (WHERE t.status IN ('completed','verified')) AS completed,
                       count(*) FILTER (WHERE {open_status} AND {due} < now()) AS overdue,
                       count(*) FILTER (WHERE t.status='cancelled') AS historical,
                       count(*) FILTER (WHERE t.status='rejected') AS rejected,
                       count(*) FILTER (WHERE t.reopen_count > 0) AS reopened,
                       round((avg(EXTRACT(EPOCH FROM (t.completed_at - t.created_at))/3600.0)
                             FILTER (WHERE t.completed_at IS NOT NULL))::numeric, 1) AS avg_hours,
                       round((100.0 * count(*) FILTER (WHERE t.completed_at IS NOT NULL
                                  AND ({due} IS NULL OR t.completed_at <= {due}))
                              / NULLIF(count(*) FILTER (WHERE t.completed_at IS NOT NULL),0))::numeric, 1) AS sla_compliance
                FROM tasks t{where_sql}""",
            params,
        )
        summary = cur.fetchone()
        cur.execute(f"SELECT t.status, count(*) AS count FROM tasks t{where_sql} GROUP BY t.status ORDER BY count DESC", params)
        by_status = cur.fetchall()
        cur.execute(f"SELECT t.priority, count(*) AS count FROM tasks t{where_sql} GROUP BY t.priority ORDER BY count DESC", params)
        by_priority = cur.fetchall()
        cur.execute(f"SELECT t.category, count(*) AS count FROM tasks t{where_sql} GROUP BY t.category ORDER BY count DESC LIMIT 12", params)
        by_category = cur.fetchall()
        cur.execute(
            f"""SELECT u.id, u.full_name,
                       count(*) AS total,
                       count(*) FILTER (WHERE {open_status} AND ({due} IS NULL OR {due} >= now())) AS active,
                       count(*) FILTER (WHERE t.status IN ('completed','verified')) AS completed,
                       count(*) FILTER (WHERE {open_status} AND {due} < now()) AS overdue,
                       count(*) FILTER (WHERE t.status='cancelled') AS historical
                FROM users u JOIN tasks t ON t.assigned_to=u.id{where_sql}
                GROUP BY u.id,u.full_name ORDER BY active DESC, total DESC""",
            params,
        )
        workload = cur.fetchall()
        cur.execute(
            f"""SELECT u.full_name, count(DISTINCT c.task_id) AS tasks,
                       sum(EXTRACT(EPOCH FROM (COALESCE(c.ended_at, now()) - c.started_at)))::bigint AS seconds
                FROM task_custody c JOIN users u ON u.id = c.holder_id
                JOIN tasks t ON t.id = c.task_id{where_sql}
                GROUP BY u.id, u.full_name ORDER BY seconds DESC LIMIT 15""",
            params,
        )
        custody = cur.fetchall()
        cur.execute(
            f"""SELECT count(*) AS n, round(avg(r.rating)::numeric, 2) AS average,
                       count(*) FILTER (WHERE r.rating=1) AS r1, count(*) FILTER (WHERE r.rating=2) AS r2,
                       count(*) FILTER (WHERE r.rating=3) AS r3, count(*) FILTER (WHERE r.rating=4) AS r4,
                       count(*) FILTER (WHERE r.rating=5) AS r5
                FROM task_ratings r JOIN tasks t ON t.id=r.task_id{where_sql}""",
            params,
        )
        rr = cur.fetchone()
        ratings = {"count": rr["n"], "average": float(rr["average"]) if rr["average"] is not None else None,
                   "distribution": {str(i): rr[f"r{i}"] for i in range(1, 6)}}
        tasks = []
        if include_tasks:
            cur.execute(
                f"""SELECT t.task_code,t.title,t.category,t.priority,t.status,
                           {due} AS due_at,t.created_at,t.completed_at,
                           r.full_name AS requester,a.full_name AS assignee
                    FROM tasks t JOIN users r ON r.id=t.created_by
                    LEFT JOIN users a ON a.id=t.assigned_to{where_sql}
                    ORDER BY t.created_at DESC LIMIT 1000""",
                params,
            )
            tasks = [{
                **dict(r),
                "due_at": _report_dt(r["due_at"]),
                "created_at": _report_dt(r["created_at"]),
                "completed_at": _report_dt(r["completed_at"]),
            } for r in cur.fetchall()]
        options = {}
        if include_options:
            cur.execute("SELECT name FROM task_categories WHERE is_active=TRUE ORDER BY lower(name)")
            categories = [r["name"] for r in cur.fetchall()]
            cur.execute("SELECT id,full_name FROM users WHERE is_active=TRUE ORDER BY full_name")
            personnel = [{"id": str(r["id"]), "full_name": r["full_name"]} for r in cur.fetchall()]
            cur.execute(
                """SELECT team FROM task_categories WHERE btrim(team) <> ''
                   UNION SELECT team FROM user_teams WHERE btrim(team) <> '' ORDER BY 1"""
            )
            teams = [r["team"] for r in cur.fetchall()]
            options = {"categories": categories, "personnel": personnel, "teams": teams}

    avg_hours = summary["avg_hours"]
    compliance = summary["sla_compliance"]
    summary["avg_hours"] = float(avg_hours) if avg_hours is not None else None
    summary["sla_compliance_pct"] = float(compliance) if compliance is not None else None
    summary["avg_resolution"] = f"{float(avg_hours):.1f} h" if avg_hours is not None else "—"
    summary["sla_compliance"] = f"{float(compliance):.1f}%" if compliance is not None else "—"
    return {
        "summary": summary,
        "byStatus": by_status,
        "byPriority": by_priority,
        "byCategory": by_category,
        "workload": workload,
        "byPersonnel": workload,
        "custodyByPerson": custody,
        "ratings": ratings,
        "tasks": tasks,
        "filters": description,
        "filterOptions": options,
    }


def _csv_safe_cell(value):
    """Stop spreadsheet formula injection from user-controlled names and titles."""
    text = "" if value is None else str(value)
    if text.startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + text
    return text


class _SafeCsvWriter:
    def __init__(self, writer):
        self._writer = writer

    def writerow(self, row):
        self._writer.writerow([_csv_safe_cell(value) for value in row])
