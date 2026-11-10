"""IT 107 registration validation: every rule and its exact message.

The same functions are used by the browser (through /api/validate) and by the
server, so turning JavaScript off cannot bypass a rule. Error messages are
worded exactly as the handout's mapping table requires.
"""

import re
from datetime import date, datetime

from app.config import (
    AUTH_QUESTION_NUMBERS,
    MAX_NAME_LENGTH,
    MAX_PASSWORD_LENGTH,
    MAX_USERNAME_LENGTH,
    MIN_PASSWORD_LENGTH,
    MIN_USERNAME_LENGTH,
    NAME_EXTENSIONS,
    OFFICE_UNITS,
)

ID_RE = re.compile(r"^\d{4}-\d{4}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
USERNAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9]*$")
PHONE_RE = re.compile(r"^09\d{9}$")
ZIP_RE = re.compile(r"^\d{4}$")
TRIPLE_RE = re.compile(r"([A-Za-z])\1\1", re.IGNORECASE)
TITLE_WORD_RE = re.compile(r"^[A-Z][a-z]*$")


def _clean(value):
    return str(value or "").strip()


def validate_name(value, label, required=True):
    text = _clean(value)
    if not text:
        return f"{label} is required." if required else None
    if len(text) < 2:
        return f"{label} must be at least 2 characters."
    if len(text) > MAX_NAME_LENGTH:
        return f"{label} must be at most {MAX_NAME_LENGTH} characters."
    if any(ch.isdigit() for ch in text):
        return f"Numbers are not allowed in {label}."
    if any(not (ch.isalpha() or ch == " ") for ch in text):
        return f"Special characters are not allowed in {label}."
    if "  " in text:
        return "Double space is not allowed."
    letters = [ch for ch in text if ch.isalpha()]
    if letters and all(ch.isupper() for ch in letters):
        return "Do not use all capital letters."
    if TRIPLE_RE.search(text):
        return "Three consecutive identical letters are not allowed."
    if not text[0].isupper():
        return "First letter of your name must be capital."
    if any(not TITLE_WORD_RE.match(word) for word in text.split(" ")):
        return "Only the first letter of each word should be capital."
    return None


def validate_name_extension(value):
    text = _clean(value)
    if not text:
        return None
    if text not in NAME_EXTENSIONS:
        return "Select a valid Name Extension."
    return None


def validate_id_number(value):
    text = _clean(value)
    if not ID_RE.match(text):
        return "ID Number must follow the format xxxx-xxxx."
    return None


def age_from_birthdate(birthdate):
    today = date.today()
    return today.year - birthdate.year - ((today.month, today.day) < (birthdate.month, birthdate.day))


def validate_birthdate(value):
    text = _clean(value)
    if not text:
        return "Birthdate is required.", None
    try:
        born = datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        return "Enter a valid birthdate.", None
    if born > date.today():
        return "Birthdate cannot be in the future.", None
    if age_from_birthdate(born) < 18:
        return "You must be at least 18 years old to register.", None
    return None, born


def _title_case_error(text, label):
    if any(not TITLE_WORD_RE.match(word) for word in text.split(" ")):
        return f"{label} must be in Title Case."
    return None


def validate_address(data):
    errors = {}

    purok = _clean(data.get("purokStreet"))
    if not purok:
        errors["purokStreet"] = "Purok / Street is required."
    elif not 3 <= len(purok) <= 50:
        errors["purokStreet"] = "Purok / Street must be 3-50 characters."
    elif any(not (ch.isalnum() or ch == " ") for ch in purok):
        errors["purokStreet"] = "Purok / Street may contain letters, digits and spaces only."
    elif "  " in purok:
        errors["purokStreet"] = "Double space is not allowed."

    for key, label in (
        ("barangay", "Barangay"),
        ("municipality", "Municipality / City"),
        ("province", "Province"),
        ("country", "Country"),
    ):
        text = _clean(data.get(key))
        if not text:
            errors[key] = f"{label} is required."
        elif not 2 <= len(text) <= 50:
            errors[key] = f"{label} must be 2-50 characters."
        elif any(not (ch.isalpha() or ch == " ") for ch in text):
            errors[key] = f"{label} may contain letters and spaces only."
        elif "  " in text:
            errors[key] = "Double space is not allowed."
        else:
            message = _title_case_error(text, label)
            if message:
                errors[key] = message

    zip_code = _clean(data.get("zipCode"))
    if not ZIP_RE.match(zip_code):
        errors["zipCode"] = "ZIP Code must be exactly 4 digits."

    return errors


def validate_email(value):
    text = _clean(value).lower()
    if not text:
        return "Email is required.", ""
    if len(text) > 100:
        return "Email must be at most 100 characters.", ""
    if " " in text or not EMAIL_RE.match(text):
        return "Please enter a valid email address.", ""
    return None, text


def validate_username(value):
    text = _clean(value)
    if not text:
        return "Username is required."
    if not USERNAME_RE.match(text):
        return "Username must start with a letter and contain only letters and digits."
    if len(text) < MIN_USERNAME_LENGTH:
        return f"Username must be at least {MIN_USERNAME_LENGTH} characters."
    if len(text) > MAX_USERNAME_LENGTH:
        return f"Username must be at most {MAX_USERNAME_LENGTH} characters."
    return None


def password_strength(password):
    """Weak / Medium / Strong. Weak cannot be submitted."""
    password = password or ""
    classes = sum(
        bool(re.search(pattern, password))
        for pattern in (r"[a-z]", r"[A-Z]", r"\d", r"[^A-Za-z0-9]")
    )
    if len(password) < MIN_PASSWORD_LENGTH or classes <= 1:
        return "Weak"
    if classes == 2:
        return "Medium"
    return "Strong"


def validate_password(password, confirm):
    password = password or ""
    if not password:
        return "Password is required."
    if len(password) < MIN_PASSWORD_LENGTH:
        return f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
    if len(password) > MAX_PASSWORD_LENGTH:
        return f"Password must be at most {MAX_PASSWORD_LENGTH} characters."
    if password_strength(password) == "Weak":
        return "Password is too weak. Use uppercase, lowercase, numbers or symbols."
    if password != (confirm or ""):
        return "Passwords do not match."
    return None


def validate_answer(value, required=True):
    text = _clean(value)
    if not text:
        return "Each security answer is required." if required else None
    if not 2 <= len(text) <= 50:
        return "Answer must be 2-50 characters."
    if any(not (ch.isalpha() or ch == " ") for ch in text):
        return "Answer may contain letters and spaces only."
    if "  " in text:
        return "Double space is not allowed."
    return None


def validate_system_fields(data):
    errors = {}

    office = _clean(data.get("officeUnit"))
    if office not in OFFICE_UNITS:
        errors["officeUnit"] = "Please select a valid Office/Unit."

    contact = _clean(data.get("contactNumber"))
    if not PHONE_RE.match(contact):
        errors["contactNumber"] = "Contact number must be 11 digits and start with 09."

    appointment = _clean(data.get("dateOfAppointment"))
    if not appointment:
        errors["dateOfAppointment"] = "Date of Appointment is required."
    else:
        try:
            appointed = datetime.strptime(appointment, "%Y-%m-%d").date()
            if appointed > date.today():
                errors["dateOfAppointment"] = "Date of Appointment cannot be in the future."
        except ValueError:
            errors["dateOfAppointment"] = "Enter a valid Date of Appointment."

    position = _clean(data.get("positionDesignation"))
    if not position:
        errors["positionDesignation"] = "Position / Designation is required."
    elif not 2 <= len(position) <= 50:
        errors["positionDesignation"] = "Position / Designation must be 2-50 characters."
    elif any(not (ch.isalpha() or ch == " ") for ch in position):
        errors["positionDesignation"] = "Position / Designation may contain letters and spaces only."
    elif "  " in position:
        errors["positionDesignation"] = "Double space is not allowed."

    return errors


def validate_registration(data):
    """Return (errors, clean, honeypot_triggered)."""
    errors = {}

    def put(key, message):
        if message and key not in errors:
            errors[key] = message

    put("idNumber", validate_id_number(data.get("idNumber")))
    put("firstName", validate_name(data.get("firstName"), "First Name"))
    put("middleName", validate_name(data.get("middleName"), "Middle Name", required=False))
    put("familyName", validate_name(data.get("familyName"), "Family Name"))
    put("nameExtension", validate_name_extension(data.get("nameExtension")))

    birth_error, birthdate = validate_birthdate(data.get("birthdate"))
    put("birthdate", birth_error)

    errors.update({k: v for k, v in validate_address(data).items() if k not in errors})

    email_error, email = validate_email(data.get("email"))
    put("email", email_error)
    put("username", validate_username(data.get("username")))
    put("password", validate_password(data.get("password"), data.get("confirmPassword")))

    answers = data.get("answers") or []
    clean_answers = []
    by_question = {}
    for item in answers:
        try:
            number = int(item.get("questionNo"))
        except (TypeError, ValueError):
            continue
        by_question[number] = item
    for number in AUTH_QUESTION_NUMBERS:
        item = by_question.get(number, {})
        answer = item.get("answer")
        confirm = item.get("confirmAnswer")
        message = validate_answer(answer)
        if not message and str(answer or "").strip().lower() != str(confirm or "").strip().lower():
            message = "Answers do not match."
        put(f"answer{number}", message)
        if not message:
            clean_answers.append({"questionNo": number, "answer": str(answer).strip().lower()})

    if not data.get("privacyConsent"):
        put("privacyConsent", "You must agree to the Privacy Notice to register.")

    errors.update({k: v for k, v in validate_system_fields(data).items() if k not in errors})

    clean = {
        "idNumber": _clean(data.get("idNumber")),
        "firstName": _clean(data.get("firstName")),
        "middleName": _clean(data.get("middleName")) or None,
        "familyName": _clean(data.get("familyName")),
        "nameExtension": _clean(data.get("nameExtension")) or None,
        "birthdate": birthdate,
        "purokStreet": _clean(data.get("purokStreet")),
        "barangay": _clean(data.get("barangay")),
        "municipality": _clean(data.get("municipality")),
        "province": _clean(data.get("province")),
        "country": _clean(data.get("country")),
        "zipCode": _clean(data.get("zipCode")),
        "officeUnit": _clean(data.get("officeUnit")),
        "contactNumber": _clean(data.get("contactNumber")),
        "dateOfAppointment": _clean(data.get("dateOfAppointment")),
        "positionDesignation": _clean(data.get("positionDesignation")),
        "email": email,
        "username": _clean(data.get("username")),
        "password": data.get("password") or "",
        "answers": clean_answers,
    }
    honeypot = bool(_clean(data.get("website")))
    return errors, clean, honeypot
