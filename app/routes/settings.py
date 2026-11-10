"""Application settings API."""

from flask import Blueprint, jsonify, request
from app.db import db
from app.permissions import login_required, roles_required
from app.services.audit import audit
from app.services.sla_engine import get_auto_close_days
from app.utils import json_error

bp = Blueprint("settings", __name__)


@bp.get("/api/settings")
@login_required
@roles_required("administrator", "coordinator")
def get_settings(user):
    with db() as conn, conn.cursor() as cur:
        return jsonify(auto_close_days=get_auto_close_days(cur))


@bp.put("/api/settings")
@login_required
@roles_required("administrator")
def update_settings(user):
    data = request.get_json(silent=True)
    days = data.get("auto_close_days") if isinstance(data, dict) else None
    if not isinstance(days, int) or isinstance(days, bool) or not 0 <= days <= 365:
        return json_error("Auto-close must be a whole number of days from 0 (never) to 365.", 400)
    with db() as conn, conn.cursor() as cur:
        cur.execute("""INSERT INTO app_settings(key,value,updated_by) VALUES ('auto_close_days',%s,%s)
                       ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value, updated_at=now(), updated_by=EXCLUDED.updated_by""",
                    (str(days), user["id"]))
        audit(cur, user["id"], "setting_updated", "system", None, f"auto_close_days = {days}")
    return jsonify(message="Saved." if days else "Saved. Completed requests will no longer close automatically.", auto_close_days=days)
