"""SMTP email delivery for OTPs and security alerts (handout sections 6.3, 9).

Required .env values:
    SMTP_HOST=smtp.gmail.com
    SMTP_PORT=587
    SMTP_USER=your.address@gmail.com
    SMTP_PASSWORD=the-16-character-Google-App-Password
    SMTP_FROM=your.address@gmail.com
    SMTP_STARTTLS=1

With no SMTP configuration, set MAIL_DEV_MODE=1 to write messages to
logs/mail_outbox.log (outside the web root) so the flow can still be tested
locally. Never enable dev mode on demo day: the handout requires real inboxes.
"""

import os
import smtplib
from email.message import EmailMessage
from pathlib import Path

from app.config import OTP_EXPIRY_MINUTES, BASE_DIR
from app.log import logger
from app.services.activity import pht_string

SYSTEM_NAME = "TaskChain"
_PURPOSE = {
    "register": ("Verify your TaskChain account", "Verify your account"),
    "login": ("Your TaskChain log-in code", "Your log-in code"),
    "reset": ("TaskChain password reset code", "Password reset code"),
}
_OUTBOX = Path(BASE_DIR) / "logs" / "mail_outbox.log"


def _smtp_configured() -> bool:
    return bool(os.environ.get("SMTP_HOST", "").strip() and os.environ.get("SMTP_FROM", "").strip())


def dev_mail_mode() -> bool:
    """True when codes are being written to logs/mail_outbox.log instead of email."""
    return os.environ.get("MAIL_DEV_MODE", "0") == "1" and not _smtp_configured()


def send_mail(to_address: str, subject: str, body: str) -> bool:
    """Send one plain-text email. Returns True when it left the process."""
    if not to_address:
        return False

    if not _smtp_configured():
        if os.environ.get("MAIL_DEV_MODE", "0") == "1":
            _OUTBOX.parent.mkdir(parents=True, exist_ok=True)
            with _OUTBOX.open("a", encoding="utf-8") as fh:
                fh.write(
                    f"\n===== {pht_string()} =====\nTo: {to_address}\n"
                    f"Subject: {subject}\n\n{body}\n"
                )
            logger.warning("SMTP is not configured; wrote message to %s", _OUTBOX)
            return True
        logger.error("SMTP is not configured and MAIL_DEV_MODE is off; email not sent")
        return False

    try:
        host = os.environ["SMTP_HOST"].strip()
        port = int(os.environ.get("SMTP_PORT", "587"))
        sender = os.environ["SMTP_FROM"].strip()
        msg = EmailMessage()
        msg["From"] = sender
        msg["To"] = to_address
        msg["Subject"] = subject
        msg.set_content(body)

        if port == 465:
            smtp = smtplib.SMTP_SSL(host, port, timeout=15)
        else:
            smtp = smtplib.SMTP(host, port, timeout=15)
        with smtp:
            if port != 465 and os.environ.get("SMTP_STARTTLS", "1") != "0":
                smtp.starttls()
            username = os.environ.get("SMTP_USER", "").strip()
            if username:
                smtp.login(username, os.environ.get("SMTP_PASSWORD", ""))
            smtp.send_message(msg)
        return True
    except Exception as exc:  # never leak SMTP details to the browser
        logger.warning("Email delivery failed: %s", type(exc).__name__)
        return False


def send_otp_email(to_address: str, purpose: str, code: str, expires_at=None) -> bool:
    heading, label = _PURPOSE.get(purpose, ("Your TaskChain code", "Your code"))
    expiry = pht_string(expires_at)
    body = (
        f"{SYSTEM_NAME}\n\n"
        f"{label}: {code}\n"
        f"This code expires in {OTP_EXPIRY_MINUTES} minutes (at {expiry}).\n\n"
        "If you did not request this code, ignore this email and consider "
        "changing your password.\n"
    )
    return send_mail(to_address, f"[{SYSTEM_NAME}] {heading}", body)


def _base_url() -> str:
    return os.environ.get("APP_BASE_URL", "http://127.0.0.1:5000").rstrip("/")


def send_security_alert(to_address: str, title: str, lines: list[str]) -> bool:
    body = f"{SYSTEM_NAME} security alert\n\n{title}\n\n" + "\n".join(lines) + (
        f"\n\nIf this was not you, reset your password now: {_base_url()}/forgot.html\n"
    )
    return send_mail(to_address, f"[{SYSTEM_NAME}] {title}", body)


def send_password_changed(to_address: str, ip_address: str, agent: str) -> bool:
    body = (
        f"{SYSTEM_NAME}\n\nYour password was changed.\n\n"
        f"Time: {pht_string()}\nIP address: {ip_address}\nBrowser: {agent or 'unknown'}\n\n"
        "If this was not you, reset your password immediately and contact an administrator.\n"
        f"Reset: {_base_url()}/forgot.html\n"
    )
    return send_mail(to_address, f"[{SYSTEM_NAME}] Your password was changed", body)
