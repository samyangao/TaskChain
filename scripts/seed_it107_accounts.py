"""Create the IT 107 demo accounts: one administrator and two users.

Run:
    python scripts/seed_it107_accounts.py

The accounts are inserted directly (never through the public registration
form), as the handout requires for administrators. Passwords are hashed with
bcrypt; the answers use the same Q4/Q7/Q1 seed.
"""

import os
import sys
from pathlib import Path

import bcrypt

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.db import db  # noqa: E402
from app.services.crypto import encrypt_field  # noqa: E402
from app.services.security_controls import remember_password  # noqa: E402

ANSWERS = ((4, "Maria"), (7, "San Jose Elementary"), (1, "Bantay"))

ADMIN_EMAIL = os.environ.get("SEED_ADMIN_EMAIL", "it107.admin@example.com").strip()
TEST1_EMAIL = os.environ.get("SEED_USER1_EMAIL", "it107.test1@example.com").strip()
TEST2_EMAIL = os.environ.get("SEED_USER2_EMAIL", "it107.test2@example.com").strip()


def required_password(name):
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(
            f"{name} is missing. Add it to .env (see .env.example); "
            "demo passwords must not be committed to Git."
        )
    return value


ADMIN_PASSWORD = required_password("SEED_ADMIN_PASSWORD")
TEST1_PASSWORD = required_password("SEED_USER1_PASSWORD")
TEST2_PASSWORD = required_password("SEED_USER2_PASSWORD")

ACCOUNTS = (
    {
        "email": ADMIN_EMAIL,
        "username": "it107admin",
        "full_name": "IT 107 Administrator",
        "password": ADMIN_PASSWORD,
        "role": "administrator",
        "profile": None,
    },
    {
        "email": TEST1_EMAIL,
        "username": "it107test1",
        "full_name": "Juan Dela Cruz",
        "password": TEST1_PASSWORD,
        "role": "requester",
        "profile": {
            "id_number": "2024-0001", "first_name": "Juan", "middle_name": None,
            "family_name": "Dela Cruz", "name_extension": None, "birthdate": "2000-01-01",
            "purok_street": "Purok 1 Mabini Street", "barangay": "Barangay San Jose",
            "municipality": "Butuan City", "province": "Agusan Del Norte",
            "country": "Philippines", "zip_code": "8600", "office_unit": "IT",
            "contact_number": "09171234567", "date_of_appointment": "2024-01-01",
            "position_designation": "Staff",
        },
    },
    {
        "email": TEST2_EMAIL,
        "username": "it107test2",
        "full_name": "Maria Santos",
        "password": TEST2_PASSWORD,
        "role": "requester",
        "profile": {
            "id_number": "2024-0002", "first_name": "Maria", "middle_name": None,
            "family_name": "Santos", "name_extension": None, "birthdate": "1999-05-05",
            "purok_street": "Purok 2 Rizal Street", "barangay": "Barangay Libertad",
            "municipality": "Butuan City", "province": "Agusan Del Norte",
            "country": "Philippines", "zip_code": "8600", "office_unit": "Finance",
            "contact_number": "09181234567", "date_of_appointment": "2023-06-01",
            "position_designation": "Staff",
        },
    },
)


def main():
    with db() as conn, conn.cursor() as cur:
        for account in ACCOUNTS:
            password_hash = bcrypt.hashpw(account["password"].encode(), bcrypt.gensalt(rounds=12)).decode()
            cur.execute("SELECT id FROM users WHERE username=%s", (account["username"],))
            row = cur.fetchone()
            if row:
                cur.execute(
                    "SELECT username FROM users WHERE email=%s AND id<>%s",
                    (account["email"], row["id"]),
                )
                if cur.fetchone():
                    raise RuntimeError(
                        f"{account['email']} is already used by another account; "
                        f"set SEED_*_EMAIL to a different inbox"
                    )
                user_id = row["id"]
                cur.execute(
                    """UPDATE users SET full_name=%s, email=%s, username=%s, password_hash=%s,
                              role=%s, is_active=TRUE, is_verified=TRUE,
                              failed_login_attempts=0, lockout_tier=0, locked_until=NULL
                        WHERE id=%s""",
                    (account["full_name"], account["email"], account["username"], password_hash,
                     account["role"], user_id),
                )
                print(f"updated {account['email']}")
            else:
                cur.execute("SELECT 1 FROM users WHERE email=%s", (account["email"],))
                if cur.fetchone():
                    raise RuntimeError(
                        f"{account['email']} is already used by a different username; "
                        f"set SEED_*_EMAIL to a different inbox"
                    )
                cur.execute(
                    """INSERT INTO users(full_name,email,password_hash,role,username,is_verified)
                       VALUES (%s,%s,%s,%s,%s,TRUE) RETURNING id""",
                    (account["full_name"], account["email"], password_hash,
                     account["role"], account["username"]),
                )
                user_id = cur.fetchone()["id"]
                print(f"created {account['email']}")

            remember_password(cur, user_id, password_hash)

            profile = account["profile"]
            if not profile:
                continue
            cur.execute("SELECT 1 FROM security_profiles WHERE id_number=%s", (profile["id_number"],))
            if cur.fetchone():
                print(f"  profile {profile['id_number']} already exists")
                continue
            contact = encrypt_field(cur, profile["contact_number"])
            cur.execute(
                """INSERT INTO security_profiles
                       (id_number,user_id,first_name,middle_name,family_name,name_extension,
                        birthdate,purok_street,barangay,municipality,province,country,zip_code,
                        office_unit,contact_number_enc,date_of_appointment,position_designation,
                        privacy_consent_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,now())""",
                (
                    profile["id_number"], user_id, profile["first_name"], profile["middle_name"],
                    profile["family_name"], profile["name_extension"], profile["birthdate"],
                    profile["purok_street"], profile["barangay"], profile["municipality"],
                    profile["province"], profile["country"], profile["zip_code"],
                    profile["office_unit"], contact, profile["date_of_appointment"],
                    profile["position_designation"],
                ),
            )
            for question_no, answer in ANSWERS:
                cur.execute(
                    """INSERT INTO security_answers(user_id,question_no,answer_hash)
                       VALUES (%s,%s,%s)
                       ON CONFLICT (user_id,question_no) DO UPDATE SET answer_hash=EXCLUDED.answer_hash""",
                    (user_id, question_no,
                     bcrypt.hashpw(answer.lower().encode(), bcrypt.gensalt(rounds=12)).decode()),
                )
            print(f"  profile {profile['id_number']} created")

    print("\nDemo credentials (change before submitting if your instructor requires different ones):")
    for account in ACCOUNTS:
        print(f"  {account['role']:<14} {account['username']:<12} {account['email']:<28} {account['password']}")


if __name__ == "__main__":
    main()
