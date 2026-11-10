"""
Activity 2 helper: create/reset the controlled admin12 laboratory account.

Usage:
  python scripts/lab_setup.py --password 05000
  python scripts/lab_setup.py --password 1234

The account is local to your PostgreSQL database. Use only for this classroom lab.
"""
import argparse, os
import bcrypt
import psycopg
from dotenv import load_dotenv

load_dotenv()

parser = argparse.ArgumentParser()
parser.add_argument("--password", required=True, help="Lab password from the Activity 2 wordlist.")
args = parser.parse_args()

password = args.password
LAB_EMAIL = "maria@gmail.com"
common = {
    "1234","12345","123456","12345678","password","password123",
    "admin","admin123","admin1234","qwerty","welcome",
    "student","student123","maria1234",
}
if not (password in common or (password.isdigit() and len(password)==5 and 0 <= int(password) <= 5000)):
    raise SystemExit("Password must be one of the Activity 2 candidates (common list or 00000-05000).")

conn = psycopg.connect(
    host=os.environ.get("DB_HOST","localhost"),
    port=os.environ.get("DB_PORT","5432"),
    dbname=os.environ.get("DB_NAME","ias_auth_demo"),
    user=os.environ.get("DB_USER","postgres"),
    password=os.environ.get("DB_PASSWORD",""),
)
pw_hash=bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()
try:
    with conn, conn.cursor() as cur:
        cur.execute("SELECT id FROM users WHERE email=%s", (LAB_EMAIL,))
        row=cur.fetchone()
        if row:
            cur.execute("""UPDATE users SET password_hash=%s, role='administrator', is_active=TRUE,
                           failed_login_attempts=0, locked_until=NULL WHERE email=%s""",
                        (pw_hash,LAB_EMAIL))
        else:
            cur.execute("""INSERT INTO users(full_name,email,password_hash,role)
                           VALUES(%s,%s,%s,%s)""",
                        ("Admin 12",LAB_EMAIL,pw_hash,"administrator"))
    print("Lab account ready: "+LAB_EMAIL)
    print("Password:", password)
finally:
    conn.close()
