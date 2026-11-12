"""Configure and test Gmail SMTP for TaskChain.

Run from the project root:

    python scripts/smtp_check.py

The script asks for the Gmail address and the 16-character App Password, tests
the SMTP login and sends one message, and only writes the settings to .env
after the test succeeds. It then sets MAIL_DEV_MODE=0.

Use --email and --to to pre-fill addresses without exposing the password in the
command line. The password is always read with getpass, never echoed.

    python scripts/smtp_check.py --email you@gmail.com --to you@gmail.com

The .env file is gitignored. This script never prints or commits the password.
"""

from __future__ import annotations

import argparse
import getpass
import smtplib
import sys
from email.message import EmailMessage
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / ".env"

DEFAULTS = {
    "SMTP_HOST": "smtp.gmail.com",
    "SMTP_PORT": "587",
    "SMTP_STARTTLS": "1",
    "MAIL_DEV_MODE": "0",
}


def read_env() -> dict[str, str]:
    values: dict[str, str] = {}
    if not ENV_PATH.exists():
        return values
    for raw in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def write_env(updates: dict[str, str]) -> None:
    """Update keys in place, preserving comments and unrelated settings."""
    lines = ENV_PATH.read_text(encoding="utf-8").splitlines() if ENV_PATH.exists() else []
    seen: set[str] = set()
    out: list[str] = []

    for raw in lines:
        stripped = raw.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            out.append(raw)
            continue
        key = stripped.split("=", 1)[0].strip()
        if key in updates:
            out.append(f"{key}={updates[key]}")
            seen.add(key)
        else:
            out.append(raw)

    if out and out[-1].strip():
        out.append("")
    for key, value in updates.items():
        if key not in seen:
            out.append(f"{key}={value}")

    ENV_PATH.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")


def send_test(*, host: str, port: int, user: str, password: str, sender: str, recipient: str) -> None:
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = recipient
    msg["Subject"] = "[TaskChain] SMTP test"
    msg.set_content(
        "TaskChain SMTP test\n\n"
        "If you received this, Gmail SMTP is working. OTP and security alert "
        "emails will now be delivered to this inbox.\n"
    )

    if port == 465:
        smtp = smtplib.SMTP_SSL(host, port, timeout=20)
    else:
        smtp = smtplib.SMTP(host, port, timeout=20)

    with smtp:
        smtp.ehlo()
        if port != 465:
            smtp.starttls()
            smtp.ehlo()
        smtp.login(user, password)
        smtp.send_message(msg)


def diagnose(exc: Exception) -> None:
    if isinstance(exc, smtplib.SMTPAuthenticationError):
        print("\nGmail rejected the login.")
        print("Use a 16-character App Password, not your normal Gmail password.")
        print("Turn on 2-Step Verification first, then create an App Password:")
        print("https://myaccount.google.com/apppasswords")
        print(f"Server response: {exc.smtp_code} {exc.smtp_error!r}")
    elif isinstance(exc, smtplib.SMTPServerDisconnected):
        print("\nGmail closed the connection during the SMTP test.")
        print("This is usually a transient network, firewall or antivirus interruption.")
        print("Try the SSL port instead:")
        print("  python scripts\\smtp_check.py --email you@gmail.com --to you@gmail.com --port 465")
    elif isinstance(exc, smtplib.SMTPConnectError):
        print("\nCould not connect to Gmail SMTP.")
        print("Check the network/firewall and that smtp.gmail.com:587 is reachable.")
    elif isinstance(exc, (TimeoutError, OSError)):
        print("\nThe connection to Gmail timed out or was refused.")
        print("Check your internet connection, VPN, firewall and antivirus.")
        print(f"Details: {type(exc).__name__}: {exc}")
    else:
        print("\nSMTP test failed.")
        print(f"Details: {type(exc).__name__}: {exc}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Configure and test Gmail SMTP for TaskChain.")
    parser.add_argument("--email", help="Gmail address used to sign in (SMTP_USER)")
    parser.add_argument("--from", dest="sender", help="From address (defaults to --email)")
    parser.add_argument("--to", dest="recipient", help="Where to send the test email (defaults to --email)")
    parser.add_argument("--host", help="SMTP host (default: smtp.gmail.com)")
    parser.add_argument("--port", type=int, help="SMTP port: 587 for STARTTLS, 465 for SSL")
    parser.add_argument("--no-write", action="store_true", help="Test only; do not update .env")
    args = parser.parse_args()

    current = read_env()
    email = (args.email or current.get("SMTP_USER") or "").strip()
    if not email:
        email = input("Gmail address: ").strip()
    if "@" not in email:
        print("That does not look like an email address.")
        return 2

    sender = (args.sender or current.get("SMTP_FROM") or email).strip()
    recipient = (args.recipient or email).strip()
    password = getpass.getpass("Google App Password (16 characters, hidden): ").replace(" ", "").strip()
    if not password:
        print("No App Password entered.")
        return 2
    if len(password) != 16:
        print(f"\nGmail App Passwords are exactly 16 characters; you entered {len(password)}.")
        print("This is usually the normal Gmail password, or an incomplete copy.")
        print("Create a new App Password at https://myaccount.google.com/apppasswords")
        print("Copy all 16 characters (remove the spaces Google displays).")
        print("\nNothing was changed; no connection was attempted.")
        return 2

    host = (args.host or current.get("SMTP_HOST") or DEFAULTS["SMTP_HOST"]).strip()
    port = args.port or int(current.get("SMTP_PORT") or DEFAULTS["SMTP_PORT"])

    print(f"\nTesting {email} via {host}:{port} ...")
    try:
        send_test(host=host, port=port, user=email, password=password, sender=sender, recipient=recipient)
    except Exception as exc:  # noqa: BLE001 - reported without the password
        diagnose(exc)
        print("\n.env was NOT changed. MAIL_DEV_MODE remains as it was.")
        return 1

    print(f"Success: test email sent to {recipient}.")
    if args.no_write:
        print("--no-write was set; .env was not changed.")
        return 0

    write_env(
        {
            "SMTP_HOST": host,
            "SMTP_PORT": str(port),
            "SMTP_STARTTLS": "1" if port != 465 else "0",
            "SMTP_USER": email,
            "SMTP_PASSWORD": password,
            "SMTP_FROM": sender,
            "MAIL_DEV_MODE": "0",
        }
    )
    print(f"Updated {ENV_PATH} (gitignored). MAIL_DEV_MODE=0.")
    print("Restart the TaskChain server so the new .env is loaded.")
    print("Then test registration, login, lockout alert and password reset.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
