"""Configuration: paths, environment-driven flags and application-wide constants."""

import os
import re
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
PAGES_DIR = FRONTEND_DIR / "pages"
UPLOAD_DIR = str(BASE_DIR / "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

_PLACEHOLDERS = {"change-this-secret-key", "replace_with_a_long_random_secret", "secret", "changeme"}


def load_secret_key():
    """Fail fast rather than silently falling back to a publicly known key.

    A leaked or missing secret lets an attacker mint arbitrary session cookies.
    """
    secret = os.environ.get("FLASK_SECRET_KEY", "").strip()
    if len(secret) < 32 or secret.lower() in _PLACEHOLDERS:
        raise RuntimeError(
            "FLASK_SECRET_KEY is missing, a placeholder, or shorter than 32 characters.\n"
            "Generate one with:  python -c \"import secrets; print(secrets.token_hex(32))\"\n"
            "Then set FLASK_SECRET_KEY in your .env file (see .env.example)."
        )
    return secret


FLASK_CONFIG = dict(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("SESSION_COOKIE_SECURE", "0") == "1",
    MAX_CONTENT_LENGTH=8 * 1024 * 1024,
    PERMANENT_SESSION_LIFETIME=timedelta(minutes=120),
    SESSION_REFRESH_EACH_REQUEST=True,
)

# The unprotected Activity 2 laboratory is opt-in and off by default.
LAB_ENABLED = os.environ.get("ENABLE_LAB", "0") == "1"
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MAX_FAILED_ATTEMPTS = 5
REPEATED_FAILED_LOGIN_THRESHOLD = 3  # admins are warned at this many failures in a row
SLA_WARNING_HOURS = 24                # "Due in 24 hours" reminder
SLA_STOPPED_STATUSES = ("completed", "cancelled", "verified")  # the SLA clock no longer matters
# Statuses the engine may replace with 'overdue'. for_verification is deliberately NOT here:
# the verifier's queue and verify() depend on that status, so such a task is only flagged.
SLA_OVERDUE_FLIPS = ("submitted", "under_review", "assigned", "accepted", "in_progress", "waiting", "handover", "rejected")
# File types accepted for attachments (evidence and handover files).
ALLOWED_UPLOAD_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".pdf", ".txt", ".doc", ".docx", ".xls", ".xlsx", ".csv"}
HANDOVER_MAX_FILES = 5  # also the limit for files on a new request
HANDOVER_MAX_FILE_BYTES = 5 * 1024 * 1024
CHECKLIST_STATES = ("done", "pending", "blocked")
DEFAULT_AUTO_CLOSE_DAYS = 7
SLA_LOCK_ID = 727301                  # advisory lock so only one process runs a check at a time

# ---------------------------------------------------------------------------
# IT 107 seed table. Student number 241-01803 -> D1 = 0, D2 = 3.
# Every timer, length and threshold below is derived from the seed; nothing in
# the security module is hardcoded, so the values can be audited against the
# handout's table.
# ---------------------------------------------------------------------------
SEED_STUDENT_NUMBER = "241-01803"
SEED_D1 = 0
SEED_D2 = 3

MIN_USERNAME_LENGTH = 6 + (SEED_D1 % 3)          # 6
MAX_USERNAME_LENGTH = 16 + (SEED_D2 % 5)         # 19
MIN_PASSWORD_LENGTH = 8 + (SEED_D2 % 4)          # 11
MAX_PASSWORD_LENGTH = 64                          # handout section 4.9
MAX_NAME_LENGTH = 20 + SEED_D2                   # 23
FORGOT_PASSWORD_AFTER = 2 + (SEED_D1 % 2)        # 2
LOCKOUT_TIER_1_SECONDS = 15 + SEED_D1            # 15
LOCKOUT_TIER_2_SECONDS = 30 + (2 * SEED_D1)      # 30
LOCKOUT_TIER_3_SECONDS = 60 + (4 * SEED_D1)      # 60
# (consecutive failures, lock seconds) -- handout section 8.3
LOCKOUT_TIERS = (
    (3, LOCKOUT_TIER_1_SECONDS),
    (6, LOCKOUT_TIER_2_SECONDS),
    (9, LOCKOUT_TIER_3_SECONDS),
)
OTP_EXPIRY_MINUTES = 3 + (SEED_D2 % 3)           # 3
IDLE_TIMEOUT_MINUTES = 5 + (SEED_D1 % 5)         # 5
IP_BLOCK_THRESHOLD = 8 + SEED_D2                 # 11 failures ...
IP_BLOCK_WINDOW_MINUTES = 10                     # ... in any 10 minutes
IP_BLOCK_MINUTES = 10                            # block lasts 10 minutes

OTP_LENGTH = 6
OTP_MAX_ATTEMPTS = 3
OTP_RESEND_COOLDOWN_SECONDS = 60
OTP_MAX_RESENDS = 3
OTP_RESEND_WINDOW_MINUTES = 15
RESET_TOKEN_MINUTES = OTP_EXPIRY_MINUTES

# Handout section 5 question bank. The three seeded questions are Q4, Q7, Q1.
AUTH_QUESTION_BANK = {
    1: "What was the name of your first pet?",
    2: "Who was your best friend in elementary school?",
    3: "Who was your favorite teacher in high school?",
    4: "What is your mother's maiden first name?",
    5: "What street did you live on in Grade 1?",
    6: "What was the first song you learned by heart?",
    7: "What was the name of your elementary school?",
    8: "What dish did you cook for the first time?",
}
AUTH_QUESTION_NUMBERS = (
    (SEED_D2 % 8) + 1,                 # Q4
    ((SEED_D2 + 3) % 8) + 1,           # Q7
    ((SEED_D2 + 5) % 8) + 1,           # Q1
)
AUTH_QUESTIONS = tuple(
    (number, AUTH_QUESTION_BANK[number]) for number in AUTH_QUESTION_NUMBERS
)

# IT 107 system fields (approved proposal).
OFFICE_UNITS = ("Registrar", "Finance", "IT", "HR", "Admin")
NAME_EXTENSIONS = ("Jr.", "Sr.", "I", "II", "III", "IV", "IX", "X")

# Existing TaskChain-wide throttle knobs (kept for non-IT107 endpoints).
LOCKOUT_MINUTES = 5
IP_MAX_ATTEMPTS = 20
IP_WINDOW_SECONDS = 300
ALLOWED_ROLES = {"requester", "coordinator", "personnel", "verifier", "administrator"}
TASK_STATUSES = {"submitted", "under_review", "assigned", "accepted", "in_progress", "waiting", "handover", "for_verification", "verified", "completed", "rejected", "cancelled", "overdue"}
# A task in one of these states is finished or waiting on a verifier, so it has no
# working holder to hand over to anyone.
HANDOVER_BLOCKED_STATUSES = {"for_verification", "verified", "completed", "cancelled"}
# Without this map any participant could PATCH their way to "completed" and
# skip the verification step entirely.
ALLOWED_TRANSITIONS = {
    "submitted":        {"under_review", "cancelled"},
    "under_review":     {"assigned", "cancelled"},
    "assigned":         {"accepted", "handover", "cancelled"},
    "accepted":         {"in_progress", "waiting", "handover", "cancelled"},
    "in_progress":      {"waiting", "handover", "for_verification", "cancelled"},
    "waiting":          {"in_progress", "handover", "cancelled"},
    "handover":         {"accepted", "in_progress", "cancelled"},
    "for_verification": {"completed", "rejected", "cancelled"},
    "verified":         {"completed"},
    "rejected":         {"in_progress", "cancelled"},
    "overdue":          {"accepted", "in_progress", "waiting", "handover", "for_verification", "cancelled"},
    "completed":        set(),
    "cancelled":        set(),
}
PRIORITIES = {"low", "medium", "high", "urgent"}
