"""Page routes: HTML pages and authorised file downloads."""

import os
from flask import Blueprint, send_from_directory, request, session
from app.config import PAGES_DIR, UPLOAD_DIR
from app.db import db
from app.permissions import current_user, is_manager, login_required
from app.services.activity import log_event
from app.utils import json_error

bp = Blueprint("pages", __name__)


@bp.get("/")
def root():
    if current_user():
        return send_from_directory(PAGES_DIR, "dashboard.html")
    return send_from_directory(PAGES_DIR, "login.html")


@bp.get("/uploads/<path:filename>")
@login_required
def uploaded_file(user, filename):
    # Authorisation, not just authentication: the caller must be able to see a
    # task that this evidence belongs to, otherwise any logged-in user could
    # download every other user's uploaded documents by name.
    stored = os.path.basename(filename)
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT t.created_by, t.assigned_to
               FROM task_evidence e JOIN tasks t ON t.id = e.task_id
               WHERE e.file_url = %(u)s
               UNION ALL
               SELECT t.created_by, t.assigned_to
               FROM task_handover_attachments a
               JOIN task_handovers h ON h.id = a.handover_id JOIN tasks t ON t.id = h.task_id
               WHERE a.file_url = %(u)s
               UNION ALL
               SELECT t.created_by, t.assigned_to
               FROM task_attachments ta JOIN tasks t ON t.id = ta.task_id
               WHERE ta.file_url = %(u)s""",
            {"u": f"/uploads/{stored}"},
        )
        owners = cur.fetchall()
    if not owners:
        return json_error("File not found.", 404)
    if not is_manager(user) and not any(user["id"] in {o["created_by"], o["assigned_to"]} for o in owners):
        return json_error("You do not have access to this file.", 403)
    inline = os.path.splitext(stored)[1].lower() in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".pdf"}
    response = send_from_directory(UPLOAD_DIR, stored, as_attachment=not inline)
    response.headers["X-Content-Type-Options"] = "nosniff"  # the browser must trust the type we declare
    return response


@bp.get("/privacy")
def privacy_alias():
    return send_from_directory(PAGES_DIR, "privacy.html")


@bp.get("/admin/security")
def admin_security_page():
    """The URL a normal user might type. Non-admins see Access denied."""
    user = current_user()
    if not user:
        return send_from_directory(PAGES_DIR, "login.html")
    if user["role"] != "administrator":
        with db() as conn, conn.cursor() as cur:
            log_event(cur, "ADMIN_ACCESS_DENIED",
                      username_typed=user.get("username") or user["email"],
                      user_id=user["id"],
                      details="Non-admin opened /admin/security")
        return "<!doctype html><h1>Access denied</h1><p>Administrator access is required.</p>", 403
    return send_from_directory(PAGES_DIR, "dashboard.html")


@bp.get("/<path:page>")
def page(page):
    if page.startswith("api/"):
        return json_error("Not found.", 404)
    allowed = {
        "login.html", "register.html", "dashboard.html", "lab_test.html",
        "privacy.html", "verify.html", "forgot.html", "reset-password.html",
    }
    if page in allowed:
        if page == "dashboard.html" and not current_user():
            return send_from_directory(PAGES_DIR, "login.html")
        if page == "verify.html" and not session.get("pending_verify_user"):
            return send_from_directory(PAGES_DIR, "login.html")
        if page == "reset-password.html" and not request.args.get("token"):
            return (
                "<!doctype html><h1>Access denied</h1>"
                "<p>Open the one-time link from your password reset email.</p>",
                403,
            )
        return send_from_directory(PAGES_DIR, page)
    return json_error("Page not found.", 404)
