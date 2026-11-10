"""Categories and SLA settings API (Phase 3)."""

import psycopg
from flask import Blueprint, jsonify, request
from app.db import db
from app.permissions import is_manager, login_required, roles_required
from app.services.audit import audit
from app.services.sla_engine import run_sla_check
from app.utils import json_error, parse_uuid

bp = Blueprint("categories", __name__)


def _category_row(r):
    return {"id": str(r["id"]), "name": r["name"], "description": r["description"],
            "default_sla_hours": r["default_sla_hours"], "escalation_hours": r["escalation_hours"],
            "team": r["team"], "is_active": r["is_active"]}


def _is_int(value, low, high):
    return isinstance(value, int) and not isinstance(value, bool) and low <= value <= high


def _category_fields(data, creating):
    """Validate a category payload. Returns (fields, error)."""
    fields = {}
    if creating:
        name = data.get("name")
        if not isinstance(name, str) or not name.strip() or len(name.strip()) > 80 or any(ord(ch) < 32 for ch in name):
            return None, "Enter a category name (up to 80 characters)."
        fields["name"] = name.strip()
    if creating or "default_sla_hours" in data:
        if not _is_int(data.get("default_sla_hours"), 1, 8760):
            return None, "SLA must be a whole number of hours between 1 and 8760."
        fields["default_sla_hours"] = data["default_sla_hours"]
    if creating or "escalation_hours" in data:
        if not _is_int(data.get("escalation_hours"), 0, 8760):
            return None, "Escalation must be a whole number of hours between 0 and 8760."
        fields["escalation_hours"] = data["escalation_hours"]
    for key, limit in (("team", 80), ("description", 255)):
        if key in data:
            if not isinstance(data[key], str) or len(data[key].strip()) > limit:
                return None, f"{key.capitalize()} must be text of up to {limit} characters."
            fields[key] = data[key].strip()
    if "is_active" in data:
        if not isinstance(data["is_active"], bool):
            return None, "Active must be true or false."
        fields["is_active"] = data["is_active"]
    return fields, None


@bp.get("/api/categories")
@login_required
def list_categories(user):
    include_inactive = request.args.get("all") == "1" and is_manager(user)
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id,name,description,default_sla_hours,escalation_hours,team,is_active FROM task_categories "
            + ("" if include_inactive else "WHERE is_active=TRUE ") + "ORDER BY lower(name)")
        rows = cur.fetchall()
    return jsonify(categories=[_category_row(r) for r in rows])


@bp.post("/api/categories")
@login_required
@roles_required("administrator")
def create_category(user):
    data = request.get_json(silent=True)
    if not isinstance(data, dict): return json_error("Send the category as a JSON object.")
    fields, error = _category_fields(data, creating=True)
    if error: return json_error(error)
    try:
        with db() as conn, conn.cursor() as cur:
            cur.execute(
                """INSERT INTO task_categories(name,description,default_sla_hours,escalation_hours,team,is_active)
                   VALUES (%s,%s,%s,%s,%s,%s)
                   RETURNING id,name,description,default_sla_hours,escalation_hours,team,is_active""",
                (fields["name"], fields.get("description", ""), fields["default_sla_hours"], fields["escalation_hours"],
                 fields.get("team", ""), fields.get("is_active", True)))
            row = cur.fetchone()
            audit(cur, user["id"], "category_created", "category", row["id"],
                  f"{row['name']}: SLA {row['default_sla_hours']}h, escalation {row['escalation_hours']}h, team '{row['team']}'")
    except psycopg.errors.UniqueViolation:
        return json_error("A category with that name already exists.", 409)
    return jsonify(message="Category created.", category=_category_row(row)), 201


@bp.put("/api/categories/<category_id>")
@login_required
@roles_required("administrator")
def update_category(user, category_id):
    if not parse_uuid(category_id): return json_error("Invalid category id.", 400)
    data = request.get_json(silent=True)
    if not isinstance(data, dict): return json_error("Send the changes as a JSON object.")
    fields, error = _category_fields(data, creating=False)
    if error: return json_error(error)
    with db() as conn, conn.cursor() as cur:
        cur.execute("SELECT id,name FROM task_categories WHERE id=%s", (category_id,))
        current = cur.fetchone()
        if not current: return json_error("Category not found.", 404)
        if "name" in data and data["name"] != current["name"]:
            return json_error("A category name cannot be changed (existing tasks use it). Create a new category and deactivate this one.")
        if not fields: return json_error("No valid changes supplied.")
        sets = ", ".join(f"{k}=%s" for k in fields)  # keys come from _category_fields, never from the client
        cur.execute(f"UPDATE task_categories SET {sets} WHERE id=%s RETURNING id,name,description,default_sla_hours,escalation_hours,team,is_active",
                    [*fields.values(), category_id])
        row = cur.fetchone()
        audit(cur, user["id"], "category_updated", "category", row["id"],
              f"{row['name']}: " + "; ".join(f"{k}={v}" for k, v in fields.items()))
    return jsonify(message="Category saved. It applies to new tasks; existing tasks keep their deadline.", category=_category_row(row))


@bp.post("/api/sla/run")
@login_required
@roles_required("administrator")
def run_sla_now(user):
    counts = run_sla_check()
    with db() as conn, conn.cursor() as cur:
        audit(cur, user["id"], "sla_check_run", "system", None, f"Manual SLA check: {counts}")
    return jsonify(counts)
