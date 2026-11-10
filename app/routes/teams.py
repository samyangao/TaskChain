"""Teams API."""

from flask import Blueprint, jsonify, request
from app.db import db
from app.permissions import login_required, roles_required
from app.services.assignment_rules import known_teams
from app.services.audit import audit
from app.utils import json_error, parse_uuid

bp = Blueprint("teams", __name__)


@bp.get("/api/teams")
@login_required
@roles_required("administrator", "coordinator")
def list_teams(user):
    with db() as conn, conn.cursor() as cur:
        names = known_teams(cur)
        cur.execute("SELECT lower(team) AS k, count(*) AS n FROM user_teams GROUP BY lower(team)")
        counts = {r["k"]: r["n"] for r in cur.fetchall()}
    return jsonify(teams=[{"name": n, "member_count": counts.get(k, 0)} for k, n in sorted(names.items())])


@bp.put("/api/users/<user_id>/teams")
@login_required
@roles_required("administrator")
def set_user_teams(user, user_id):
    if not parse_uuid(user_id): return json_error("Invalid user id.", 400)
    data = request.get_json(silent=True)
    teams = data.get("teams") if isinstance(data, dict) else None
    if not isinstance(teams, list) or len(teams) > 20 or not all(isinstance(t, str) for t in teams):
        return json_error("Send teams as a list of team names.", 400)
    with db() as conn, conn.cursor() as cur:
        cur.execute("SELECT id, full_name FROM users WHERE id=%s", (user_id,))
        target = cur.fetchone()
        if not target: return json_error("User not found.", 404)
        known = known_teams(cur)
        chosen = {}
        for name in teams:
            key = name.strip().lower()
            if key not in known:
                return json_error(f"Unknown team: {name.strip()[:40] or '(blank)'}. Teams come from the categories under SLA Settings.", 400)
            chosen[key] = known[key]
        cur.execute("DELETE FROM user_teams WHERE user_id=%s", (user_id,))
        for name in chosen.values():
            cur.execute("INSERT INTO user_teams(user_id, team) VALUES (%s,%s)", (user_id, name))
        audit(cur, user["id"], "user_teams_updated", "user", user_id, f"{target['full_name']}: " + (", ".join(chosen.values()) or "no teams"))
    return jsonify(message="Teams saved.", teams=sorted(chosen.values(), key=str.lower))
