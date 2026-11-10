"""Request hooks: security headers, CSRF, idle-session timeout and notifications."""

import threading

from flask import current_app, g, jsonify, request, session

from app.config import LAB_ENABLED
from app.db import db
from app.services.activity import log_event
from app.services.notification_delivery import _deliver_external, external_channels
from app.services.security_controls import (
    csrf_valid,
    ensure_csrf_token,
    touch_session,
)
from app.utils import json_error

# Background polling must not keep an idle session alive.
_IDLE_EXEMPT = {
    "/api/session/status",
    "/api/notifications/unread",
    "/api/notifications",
}


def dispatch_external_notifications(response):
    items = g.pop("notify_outbox", None)
    if items and any(external_channels().values()):
        threading.Thread(target=_deliver_external, args=(items,), daemon=True).start()
    return response


def security_before_request():
    path = request.path
    if path.startswith("/static/"):
        return None

    touch_session(update=path not in _IDLE_EXEMPT)
    g.csrf_token = ensure_csrf_token()

    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        # The classroom brute-force lab posts directly to /api/login; it is
        # exempt only while ENABLE_LAB=1. On the real project it is protected.
        lab_exempt = LAB_ENABLED and path in {"/api/login", "/api/lab-login"}
        if not lab_exempt and not csrf_valid(request.headers.get("X-CSRF-Token")):
            try:
                with db() as conn, conn.cursor() as cur:
                    log_event(
                        cur,
                        "CSRF_REJECTED",
                        username_typed=session.get("pending_verify_name") or session.get("pending_login_name"),
                        details=f"{request.method} {path} rejected: token missing or invalid",
                    )
            except Exception:
                pass
            return json_error("Security token missing or invalid. Refresh the page and try again.", 403)
    return None


def security_after_request(response):
    token = getattr(g, "csrf_token", None)
    if token:
        response.set_cookie(
            "csrf_token",
            token,
            httponly=False,
            samesite="Lax",
            secure=bool(current_app.config.get("SESSION_COOKIE_SECURE")),
        )
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    if not request.path.startswith("/static/"):
        # Protected pages must not be restored from the browser cache after logout.
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    return response


def register_hooks(app):
    app.before_request(security_before_request)
    app.after_request(security_after_request)
    app.after_request(dispatch_external_notifications)
