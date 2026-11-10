"""Optional external delivery of notifications: email and webhooks (Phase 2b)."""

import os
import smtplib
from email.message import EmailMessage
from uuid import UUID
from app.db import db
from app.log import logger


# Everything below is off unless the matching environment variables are set, and
# a failure never reaches the user: it is logged (type of error only, because a
# webhook URL is a secret) and the app carries on.
def external_channels():
    def https(value):
        return value.strip().lower().startswith("https://")
    return {
        "email": bool(os.environ.get("SMTP_HOST", "").strip() and os.environ.get("SMTP_FROM", "").strip()),
        "teams": https(os.environ.get("TEAMS_WEBHOOK_URL", "")),
        "slack": https(os.environ.get("SLACK_WEBHOOK_URL", "")),
    }


def _send_email(to_address, title, message, code):
    try:
        host = os.environ["SMTP_HOST"].strip()
        port = int(os.environ.get("SMTP_PORT", "587"))
        msg = EmailMessage()
        msg["From"] = os.environ["SMTP_FROM"].strip()
        msg["To"] = to_address
        msg["Subject"] = f"[TaskChain] {title}" + (f" - {code}" if code else "")
        msg.set_content(f"{message}\n\nOpen TaskChain to see the details.")
        smtp = smtplib.SMTP_SSL(host, port, timeout=10) if port == 465 else smtplib.SMTP(host, port, timeout=10)
        with smtp:
            if port != 465 and os.environ.get("SMTP_STARTTLS", "1") != "0":
                smtp.starttls()
            username = os.environ.get("SMTP_USER", "").strip()
            if username:
                smtp.login(username, os.environ.get("SMTP_PASSWORD", ""))
            smtp.send_message(msg)
    except Exception as exc:
        logger.warning("Email notification failed: %s", type(exc).__name__)


def _post_webhook(env_name, payload, label):
    try:
        import requests
        resp = requests.post(os.environ[env_name].strip(), json=payload, timeout=10, allow_redirects=False)
        if resp.status_code >= 400:
            logger.warning("%s webhook returned HTTP %s", label, resp.status_code)
    except Exception as exc:
        logger.warning("%s webhook failed: %s", label, type(exc).__name__)


def _channel_text(title, code, recipient_name):
    text = f"[TaskChain] {title}" + (f" · {code}" if code else "") + f" (for {recipient_name})"
    return " ".join(text.split())


def _deliver_external(items):
    """Runs in a background thread after the HTTP response has been sent."""
    try:
        channels = external_channels()
        with db() as conn, conn.cursor() as cur:
            # Only deliver what was really committed (a rolled-back action leaves no row).
            cur.execute("SELECT id FROM notifications WHERE id = ANY(%s)", ([i["id"] for i in items],))
            committed = {r["id"] for r in cur.fetchall()}
            items = [i for i in items if i["id"] in committed]
            if not items:
                return
            user_ids = list({UUID(str(i["user_id"])) for i in items})
            cur.execute(
                """SELECT u.id, u.full_name, u.email AS address, p.email, p.teams, p.slack
                   FROM notification_preferences p JOIN users u ON u.id = p.user_id
                   WHERE u.id = ANY(%s) AND u.is_active=TRUE""",
                (user_ids,),
            )
            prefs = {r["id"]: r for r in cur.fetchall()}
            task_ids = list({UUID(str(i["task_id"])) for i in items if i["task_id"]})
            codes = {}
            if task_ids:
                cur.execute("SELECT id, task_code FROM tasks WHERE id = ANY(%s)", (task_ids,))
                codes = {r["id"]: r["task_code"] for r in cur.fetchall()}
    except Exception as exc:
        logger.warning("External notification lookup failed: %s", type(exc).__name__)
        return
    for item in items:
        pref = prefs.get(UUID(str(item["user_id"])))
        if not pref:
            continue
        code = codes.get(UUID(str(item["task_id"]))) if item["task_id"] else None
        if channels["email"] and pref["email"]:
            _send_email(str(pref["address"]), item["title"], item["message"], code)
        # Webhook posts go to a shared channel: no message body, only title, task code
        # and who it is for. Slack treats &, < and > specially (<!channel> would ping everyone).
        text = _channel_text(item["title"], code, pref["full_name"])
        if channels["teams"] and pref["teams"]:
            _post_webhook("TEAMS_WEBHOOK_URL", {
                "type": "message",
                "attachments": [{
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "content": {
                        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                        "type": "AdaptiveCard", "version": "1.2",
                        "body": [{"type": "TextBlock", "text": text, "wrap": True}],
                    },
                }],
            }, "Teams")
        if channels["slack"] and pref["slack"]:
            safe = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            _post_webhook("SLACK_WEBHOOK_URL", {"text": safe}, "Slack")
