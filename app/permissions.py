"""Current-user lookup, login/role decorators and task-visibility checks."""

from flask import session
from functools import wraps
from app.db import db
from app.utils import json_error, parse_uuid


def is_manager(user):
    return user["role"] in {"administrator", "coordinator"}


def can_view_task(user, task):
    """Managers see everything; everyone else only their own tasks."""
    if is_manager(user):
        return True
    return user["id"] in {task["created_by"], task["assigned_to"]}


def current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    if not parse_uuid(uid):
        session.clear()
        return None
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT id, full_name, email, username, role, is_active, is_verified,
                      created_at, last_login_at, session_version, totp_enabled,
                      password_changed_at, failed_login_attempts, locked_until, lockout_tier
               FROM users WHERE id=%s""",
            (uid,),
        )
        user = cur.fetchone()
    if not user or not user["is_active"]:
        session.clear()
        return None
    # "Sign out everywhere" and password changes bump session_version. A cookie
    # minted before that bump no longer matches, so it stops working immediately.
    if int(session.get("sv", 0)) != int(user["session_version"] or 0):
        session.clear()
        return None
    return user


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = current_user()
        if not user:
            return json_error("Authentication required.", 401)
        return fn(user, *args, **kwargs)
    return wrapper


def roles_required(*roles):
    def decorator(fn):
        @wraps(fn)
        def wrapper(user, *args, **kwargs):
            if user["role"] not in roles:
                return json_error("You do not have permission to perform this action.", 403)
            return fn(user, *args, **kwargs)
        return wrapper
    return decorator
