"""User management API."""

from flask import Blueprint, jsonify, request
from app.config import ALLOWED_ROLES
from app.db import db
from app.permissions import login_required
from app.services.audit import audit
from app.utils import json_error, parse_uuid

bp = Blueprint("users", __name__)


@bp.get("/api/users")
@login_required
def users(user):
    if user["role"] not in {"administrator", "coordinator"}:
        return json_error("You do not have permission to view users.", 403)
    with db() as conn, conn.cursor() as cur:
        cur.execute("SELECT id,full_name,email,role,is_active,last_login_at,created_at FROM users ORDER BY full_name")
        rows = cur.fetchall()
        cur.execute("SELECT user_id, team FROM user_teams ORDER BY lower(team)")
        teams_by_user = {}
        for t in cur.fetchall():
            teams_by_user.setdefault(t["user_id"], []).append(t["team"])
    return jsonify(users=[{**r,"id":str(r["id"]),"teams":teams_by_user.get(r["id"],[])} for r in rows])


@bp.patch("/api/users/<user_id>")
@login_required
def update_user(user, user_id):
    if user["role"] != "administrator":
        return json_error("Administrator permission required.", 403)
    data = request.get_json(silent=True) or {}
    role = (data.get("role") or "").lower()
    if role not in ALLOWED_ROLES:
        return json_error("Invalid role.")
    active = data.get("isActive")
    if not isinstance(active, bool):
        return json_error("isActive must be true or false.")

    target_id = parse_uuid(user_id)
    if not target_id:
        return json_error("Invalid user id.", 400)
    # Never allow an administrator to demote or deactivate their own account,
    # which would leave the system with no way back in.
    if target_id == user["id"]:
        return json_error("You cannot change your own role or activation status.", 400)

    with db() as conn, conn.cursor() as cur:
        cur.execute("SELECT id,role,is_active FROM users WHERE id=%s", (target_id,))
        target = cur.fetchone()
        if not target:
            return json_error("User not found.",404)
        # Refuse to remove the last active administrator account.
        if target["role"] == "administrator" and (role != "administrator" or not active):
            cur.execute("SELECT count(*) AS n FROM users WHERE role='administrator' AND is_active=TRUE")
            if cur.fetchone()["n"] <= 1:
                return json_error("At least one active administrator must remain.", 409)
        cur.execute("UPDATE users SET role=%s,is_active=%s WHERE id=%s", (role,active,target_id))
        audit(cur,user["id"],"user_updated","user",str(target_id),f"role={role}; active={active}")
    return jsonify(message="User updated.")
