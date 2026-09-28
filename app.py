import os
import re
from datetime import datetime, timedelta, timezone
from functools import wraps
from uuid import UUID

import bcrypt
import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv
from flask import Flask, jsonify, request, session, send_from_directory, send_file
from werkzeug.utils import secure_filename

load_dotenv()

app = Flask(__name__, static_folder="static", static_url_path="")
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "change-this-secret-key")
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("SESSION_COOKIE_SECURE", "0") == "1",
    MAX_CONTENT_LENGTH=8 * 1024 * 1024,
)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 5
ALLOWED_ROLES = {"requester", "coordinator", "personnel", "verifier", "administrator"}
TASK_STATUSES = {"submitted", "under_review", "assigned", "accepted", "in_progress", "waiting", "handover", "for_verification", "verified", "completed", "rejected", "cancelled", "overdue"}
PRIORITIES = {"low", "medium", "high", "urgent"}


def db():
    return psycopg.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        port=os.environ.get("DB_PORT", "5432"),
        dbname=os.environ.get("DB_NAME", "ias_auth_demo"),
        user=os.environ.get("DB_USER", "postgres"),
        password=os.environ.get("DB_PASSWORD", ""),
        row_factory=dict_row,
    )


def json_error(message, status=400):
    return jsonify(error=message), status


def current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    try:
        UUID(uid)
    except ValueError:
        session.clear()
        return None
    with db() as conn, conn.cursor() as cur:
        cur.execute("SELECT id, full_name, email, role, is_active, created_at, last_login_at FROM users WHERE id=%s", (uid,))
        user = cur.fetchone()
    if not user or not user["is_active"]:
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


def audit(cur, actor_id, action, entity_type=None, entity_id=None, details=None):
    cur.execute(
        "INSERT INTO audit_logs(actor_id, action, entity_type, entity_id, details) VALUES (%s,%s,%s,%s,%s)",
        (actor_id, action, entity_type, entity_id, details),
    )


def notify(cur, user_id, title, message, task_id=None, kind="system"):
    cur.execute(
        "INSERT INTO notifications(user_id,title,message,task_id,kind) VALUES (%s,%s,%s,%s,%s)",
        (user_id, title, message, task_id, kind),
    )


# ---------- Pages ----------
@app.get("/")
def root():
    if current_user():
        return send_from_directory(app.static_folder, "dashboard.html")
    return send_from_directory(app.static_folder, "login.html")


@app.get("/uploads/<path:filename>")
@login_required
def uploaded_file(user, filename):
    return send_from_directory(UPLOAD_DIR, filename)


@app.get("/<path:page>")
def page(page):
    if page.startswith("api/"):
        return json_error("Not found.", 404)
    allowed = {"login.html", "register.html", "dashboard.html", "lab_test.html"}
    if page in allowed:
        if page == "dashboard.html" and not current_user():
            return send_from_directory(app.static_folder, "login.html")
        return send_from_directory(app.static_folder, page)
    return json_error("Page not found.", 404)


# ---------- Authentication ----------
@app.post("/api/register")
def register():
    data = request.get_json(silent=True) or {}
    full_name = (data.get("fullName") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    role = (data.get("role") or "requester").strip().lower()

    if not full_name or len(full_name) > 120:
        return json_error("Enter a valid full name.")
    if not EMAIL_RE.match(email) or len(email) > 320:
        return json_error("Enter a valid email address.")
    if len(password) < 8:
        return json_error("Password must be at least 8 characters.")
    # Public registration can only create requester accounts.
    role = "requester"

    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()
    try:
        with db() as conn, conn.cursor() as cur:
            cur.execute("SELECT 1 FROM users WHERE email=%s", (email,))
            if cur.fetchone():
                return json_error("That email is already registered.", 409)
            cur.execute("INSERT INTO users(full_name,email,password_hash,role) VALUES(%s,%s,%s,%s) RETURNING id", (full_name,email,password_hash,role))
            uid = cur.fetchone()["id"]
            audit(cur, uid, "account_registered", "user", uid, "Public registration")
        return jsonify(message="Account created."), 201
    except psycopg.Error:
        return json_error("Unable to create the account right now.", 500)


@app.post("/api/login")
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    if not email or not password:
        return json_error("Enter both an email and a password.")

    with db() as conn, conn.cursor() as cur:
        cur.execute("SELECT id,full_name,email,password_hash,failed_login_attempts,locked_until,is_active,role FROM users WHERE email=%s", (email,))
        user = cur.fetchone()
        generic = "That email and password combination didn't work."
        if not user or not user["is_active"]:
            cur.execute("INSERT INTO login_attempts(email,success,ip_address) VALUES(%s,%s,%s)", (email,False,request.remote_addr))
            return json_error(generic, 401)
        now = datetime.now(timezone.utc)
        if user["locked_until"] and user["locked_until"] > now:
            remaining_seconds = max(1, int((user["locked_until"] - now).total_seconds()))
            return jsonify(
                error="Too many failed attempts. This account is locked for 5 minutes.",
                lockedUntil=user["locked_until"].isoformat(),
                retryAfterSeconds=remaining_seconds,
            ), 429
        if user["locked_until"]:
            # A completed lockout starts a new set of allowed attempts.
            cur.execute("UPDATE users SET failed_login_attempts=0,locked_until=NULL WHERE id=%s", (user["id"],))
            user["failed_login_attempts"] = 0
            user["locked_until"] = None
        valid = bcrypt.checkpw(password.encode(), user["password_hash"].encode())
        if not valid:
            attempts = user["failed_login_attempts"] + 1
            locked = now + timedelta(minutes=LOCKOUT_MINUTES) if attempts >= MAX_FAILED_ATTEMPTS else None
            cur.execute("UPDATE users SET failed_login_attempts=%s,locked_until=%s WHERE id=%s", (attempts,locked,user["id"]))
            cur.execute("INSERT INTO login_attempts(email,success,ip_address) VALUES(%s,%s,%s)", (email,False,request.remote_addr))
            if locked:
                return jsonify(
                    error="Too many failed attempts. This account is locked for 5 minutes.",
                    attemptsLeft=0,
                    lockedUntil=locked.isoformat(),
                    retryAfterSeconds=LOCKOUT_MINUTES * 60,
                ), 429
            attempts_left = MAX_FAILED_ATTEMPTS - attempts
            return jsonify(error=generic, attemptsLeft=attempts_left), 401
        cur.execute("UPDATE users SET failed_login_attempts=0,locked_until=NULL,last_login_at=now() WHERE id=%s", (user["id"],))
        cur.execute("INSERT INTO login_attempts(email,success,ip_address) VALUES(%s,%s,%s)", (email,True,request.remote_addr))
        audit(cur, user["id"], "login_success", "user", user["id"], "Successful login")
        session.clear()
        session["user_id"] = str(user["id"])
    return jsonify(message="Login successful.", user={"id":str(user["id"]),"fullName":user["full_name"],"email":user["email"],"role":user["role"]})

# ---------- Activity 2: Unprotected localhost laboratory login ----------
@app.post("/api/lab-login")
def lab_login():
    # This endpoint exists ONLY for the Activity 2 localhost laboratory.
    # It intentionally has NO rate limiting or account lockout.
    
    if request.remote_addr not in {"127.0.0.1", "::1"}:
        return json_error("Unprotected lab is restricted to localhost.", 403)

    data = request.get_json(silent=True) or {}

    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        return json_error("Enter both an email and a password.", 400)

    with db() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, full_name, email, password_hash, is_active, role
            FROM users
            WHERE email=%s
            """,
            (email,)
        )

        user = cur.fetchone()

        if not user or not user["is_active"]:
            return json_error("Invalid login credentials.", 401)

        valid = bcrypt.checkpw(
            password.encode(),
            user["password_hash"].encode()
        )

        if not valid:
            # IMPORTANT:
            # Do NOT increase failed_login_attempts.
            # Do NOT set locked_until.
            return json_error("Invalid login credentials.", 401)

    return jsonify(
        message="Lab login successful.",
        user={
            "id": str(user["id"]),
            "fullName": user["full_name"],
            "email": user["email"],
            "role": user["role"]
        }
    ), 200


@app.post("/api/logout")
@login_required
def logout(user):
    session.clear()
    return jsonify(message="Logged out.")


@app.get("/api/me")
@login_required
def me(user):
    return jsonify(user={**user, "id": str(user["id"])})


# ---------- Dashboard ----------
@app.get("/api/dashboard")
@login_required
def dashboard(user):
    with db() as conn, conn.cursor() as cur:
        if user["role"] in {"administrator", "coordinator"}:
            cur.execute("SELECT count(*) AS n FROM tasks"); total = cur.fetchone()["n"]
            cur.execute("SELECT status,count(*) AS n FROM tasks GROUP BY status"); status_rows = cur.fetchall()
            cur.execute("SELECT count(*) AS n FROM tasks WHERE deadline < now() AND status NOT IN ('completed','cancelled')"); overdue = cur.fetchone()["n"]
            cur.execute("SELECT count(*) AS n FROM tasks WHERE status='for_verification'"); verification = cur.fetchone()["n"]
            scope = "all"
        else:
            cur.execute("SELECT count(*) AS n FROM tasks WHERE created_by=%s OR assigned_to=%s", (user["id"],user["id"])); total = cur.fetchone()["n"]
            cur.execute("SELECT status,count(*) AS n FROM tasks WHERE created_by=%s OR assigned_to=%s GROUP BY status", (user["id"],user["id"])); status_rows = cur.fetchall()
            cur.execute("SELECT count(*) AS n FROM tasks WHERE deadline < now() AND status NOT IN ('completed','cancelled') AND (created_by=%s OR assigned_to=%s)", (user["id"],user["id"])); overdue = cur.fetchone()["n"]
            cur.execute("SELECT count(*) AS n FROM tasks WHERE status='for_verification' AND (created_by=%s OR assigned_to=%s)", (user["id"],user["id"])); verification = cur.fetchone()["n"]
            scope = "mine"
        cur.execute("""SELECT t.id,t.task_code,t.title,t.priority,t.status,t.deadline,t.updated_at,
                       r.full_name AS requester,a.full_name AS assignee
                       FROM tasks t JOIN users r ON r.id=t.created_by
                       LEFT JOIN users a ON a.id=t.assigned_to
                       WHERE (%s='all' OR t.created_by=%s OR t.assigned_to=%s)
                       ORDER BY t.updated_at DESC LIMIT 8""", (scope,user["id"],user["id"]))
        recent = cur.fetchall()
        cur.execute("SELECT id,title,message,created_at,is_read FROM notifications WHERE user_id=%s ORDER BY created_at DESC LIMIT 5", (user["id"],))
        notifications = cur.fetchall()
    counts = {r["status"]: r["n"] for r in status_rows}
    return jsonify(summary={"total":total,"new_requests":counts.get("submitted",0),"in_progress":counts.get("in_progress",0)+counts.get("accepted",0),"waiting":counts.get("waiting",0),"handover":counts.get("handover",0),"verification":verification,"completed":counts.get("completed",0),"overdue":overdue}, recent=recent, notifications=notifications)


# ---------- Users ----------
@app.get("/api/users")
@login_required
def users(user):
    if user["role"] not in {"administrator", "coordinator"}:
        return json_error("You do not have permission to view users.", 403)
    with db() as conn, conn.cursor() as cur:
        cur.execute("SELECT id,full_name,email,role,is_active,last_login_at,created_at FROM users ORDER BY full_name")
        rows = cur.fetchall()
    return jsonify(users=[{**r,"id":str(r["id"])} for r in rows])


@app.patch("/api/users/<user_id>")
@login_required
def update_user(user, user_id):
    if user["role"] != "administrator":
        return json_error("Administrator permission required.", 403)
    data = request.get_json(silent=True) or {}
    role = (data.get("role") or "").lower()
    if role not in ALLOWED_ROLES:
        return json_error("Invalid role.")
    active = data.get("isActive")
    if not isinstance(active, bool):
        return json_error("isActive must be true or false.")
    with db() as conn, conn.cursor() as cur:
        cur.execute("SELECT id FROM users WHERE id=%s", (user_id,))
        if not cur.fetchone(): return json_error("User not found.",404)
        cur.execute("UPDATE users SET role=%s,is_active=%s WHERE id=%s", (role,active,user_id))
        audit(cur,user["id"],"user_updated","user",user_id,f"role={role}; active={active}")
    return jsonify(message="User updated.")


# ---------- Tasks ----------
TASK_SELECT = """SELECT t.id,t.task_code,t.title,t.description,t.category,t.priority,t.status,t.deadline,t.location,t.created_at,t.updated_at,
                         t.created_by,t.assigned_to,r.full_name AS requester,r.email AS requester_email,
                         a.full_name AS assignee,a.email AS assignee_email
                  FROM tasks t JOIN users r ON r.id=t.created_by LEFT JOIN users a ON a.id=t.assigned_to"""


def task_dict(row):
    if not row: return None
    out = dict(row)
    out["id"] = str(out["id"])
    if out.get("created_by"): out["created_by"] = str(out["created_by"])
    if out.get("assigned_to"): out["assigned_to"] = str(out["assigned_to"])
    return out


@app.get("/api/tasks")
@login_required
def tasks(user):
    status = request.args.get("status")
    q = (request.args.get("q") or "").strip()
    with db() as conn, conn.cursor() as cur:
        where, params = [], []
        if user["role"] not in {"administrator","coordinator"}:
            where.append("(t.created_by=%s OR t.assigned_to=%s)"); params += [user["id"],user["id"]]
        if status and status in TASK_STATUSES:
            where.append("t.status=%s"); params.append(status)
        if q:
            where.append("(t.task_code ILIKE %s OR t.title ILIKE %s OR r.full_name ILIKE %s OR COALESCE(a.full_name,'') ILIKE %s)")
            like=f"%{q}%"; params += [like,like,like,like]
        sql = TASK_SELECT + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY t.updated_at DESC"
        cur.execute(sql, params); rows=cur.fetchall()
    return jsonify(tasks=[task_dict(r) for r in rows])


@app.post("/api/tasks")
@login_required
def create_task(user):
    data=request.get_json(silent=True) or {}
    title=(data.get("title") or "").strip(); description=(data.get("description") or "").strip()
    category=(data.get("category") or "General").strip(); priority=(data.get("priority") or "medium").lower(); deadline=data.get("deadline") or None; location=(data.get("location") or "").strip() or None
    if not title or len(title)>160: return json_error("Task title is required.")
    if priority not in PRIORITIES: return json_error("Invalid priority.")
    with db() as conn, conn.cursor() as cur:
        cur.execute("SELECT 'TC-' || lpad(nextval('task_code_seq')::text,6,'0') AS code")
        code=cur.fetchone()["code"]
        cur.execute("""INSERT INTO tasks(task_code,title,description,category,priority,status,deadline,location,created_by)
                       VALUES(%s,%s,%s,%s,%s,'submitted',%s,%s,%s) RETURNING id""",(code,title,description,category,priority,deadline,location,user["id"]))
        tid=cur.fetchone()["id"]
        audit(cur,user["id"],"task_created","task",tid,f"Task {code} created")
        # Coordinators/admins receive the request.
        cur.execute("SELECT id FROM users WHERE role IN ('administrator','coordinator') AND is_active=TRUE")
        for recipient in cur.fetchall(): notify(cur,recipient["id"],"New task request",f"{user['full_name']} submitted {code}.",tid,"task")
    return jsonify(message="Task created.", taskId=str(tid), taskCode=code),201


@app.get("/api/tasks/<task_id>")
@login_required
def get_task(user, task_id):
    with db() as conn, conn.cursor() as cur:
        cur.execute(TASK_SELECT + " WHERE t.id=%s", (task_id,)); task=cur.fetchone()
        if not task: return json_error("Task not found.",404)
        if user["role"] not in {"administrator","coordinator"} and user["id"] not in {task["created_by"],task["assigned_to"]}: return json_error("You do not have access to this task.",403)
        cur.execute("SELECT h.*, f.full_name AS from_name, t.full_name AS to_name FROM task_handovers h JOIN users f ON f.id=h.from_user_id JOIN users t ON t.id=h.to_user_id WHERE h.task_id=%s ORDER BY h.created_at", (task_id,)); handovers=cur.fetchall()
        cur.execute("SELECT e.*,u.full_name AS uploader FROM task_evidence e JOIN users u ON u.id=e.uploaded_by WHERE e.task_id=%s ORDER BY e.created_at DESC", (task_id,)); evidence=cur.fetchall()
        cur.execute("SELECT v.*,u.full_name AS verifier_name FROM task_verifications v JOIN users u ON u.id=v.verifier_id WHERE v.task_id=%s ORDER BY v.created_at DESC", (task_id,)); verifications=cur.fetchall()
        cur.execute("SELECT c.*,u.full_name AS author_name FROM task_comments c JOIN users u ON u.id=c.author_id WHERE c.task_id=%s ORDER BY c.created_at", (task_id,)); comments=cur.fetchall()
        cur.execute("SELECT l.*,u.full_name AS actor_name FROM audit_logs l LEFT JOIN users u ON u.id=l.actor_id WHERE l.entity_type='task' AND l.entity_id=%s ORDER BY l.created_at", (task_id,)); activity=cur.fetchall()
    def normalize(rows):
        result=[]
        for r in rows:
            x=dict(r)
            for k,v in list(x.items()):
                if hasattr(v,'hex') and k.endswith('_id'): x[k]=str(v)
            result.append(x)
        return result
    return jsonify(task=task_dict(task),handovers=normalize(handovers),evidence=normalize(evidence),verifications=normalize(verifications),comments=normalize(comments),activity=normalize(activity))


@app.patch("/api/tasks/<task_id>")
@login_required
def update_task(user, task_id):
    data=request.get_json(silent=True) or {}
    with db() as conn, conn.cursor() as cur:
        cur.execute("SELECT id,task_code,status,assigned_to,created_by FROM tasks WHERE id=%s",(task_id,)); task=cur.fetchone()
        if not task: return json_error("Task not found.",404)
        allowed_fields={}
        if "status" in data and data["status"] in TASK_STATUSES: allowed_fields["status"]=data["status"]
        if "priority" in data and data["priority"] in PRIORITIES: allowed_fields["priority"]=data["priority"]
        if "deadline" in data: allowed_fields["deadline"]=data["deadline"] or None
        if "category" in data: allowed_fields["category"]=(data["category"] or "General").strip()
        if "description" in data: allowed_fields["description"]=(data["description"] or "").strip()
        if not allowed_fields: return json_error("No valid changes supplied.")
        is_manager=user["role"] in {"administrator","coordinator"}
        if not is_manager and user["id"] not in {task["created_by"],task["assigned_to"]}: return json_error("You do not have permission to update this task.",403)
        sets=[]; params=[]
        for k,v in allowed_fields.items(): sets.append(f"{k}=%s"); params.append(v)
        params.append(task_id)
        cur.execute(f"UPDATE tasks SET {','.join(sets)} WHERE id=%s",params)
        audit(cur,user["id"],"task_updated","task",task_id,"; ".join(f"{k}={v}" for k,v in allowed_fields.items()))
    return jsonify(message="Task updated.")


@app.post("/api/tasks/<task_id>/assign")
@login_required
@roles_required("administrator","coordinator")
def assign_task(user, task_id):
    data=request.get_json(silent=True) or {}; assignee=data.get("assignedTo")
    if not assignee: return json_error("Select a personnel account.")
    with db() as conn, conn.cursor() as cur:
        cur.execute("SELECT id,task_code FROM tasks WHERE id=%s",(task_id,)); task=cur.fetchone()
        cur.execute("SELECT id,full_name FROM users WHERE id=%s AND is_active=TRUE",(assignee,)); target=cur.fetchone()
        if not task or not target: return json_error("Task or user not found.",404)
        cur.execute("UPDATE tasks SET assigned_to=%s,status='assigned' WHERE id=%s",(assignee,task_id))
        notify(cur,target["id"],"Task assigned",f"You have been assigned {task['task_code']}.",task_id,"assignment")
        audit(cur,user["id"],"task_assigned","task",task_id,f"Assigned to {target['full_name']}")
    return jsonify(message="Task assigned.")


@app.post("/api/tasks/<task_id>/handover")
@login_required
def handover(user, task_id):
    data=request.get_json(silent=True) or {}; to_user=data.get("toUser"); reason=(data.get("reason") or "").strip(); notes=(data.get("notes") or "").strip()
    if not to_user or not reason: return json_error("Recipient and handover reason are required.")
    with db() as conn, conn.cursor() as cur:
        cur.execute("SELECT id,task_code,assigned_to,created_by,status FROM tasks WHERE id=%s",(task_id,)); task=cur.fetchone()
        cur.execute("SELECT id,full_name FROM users WHERE id=%s AND is_active=TRUE",(to_user,)); target=cur.fetchone()
        if not task or not target: return json_error("Task or recipient not found.",404)
        if task["assigned_to"] != user["id"] and user["role"] not in {"administrator","coordinator"}: return json_error("Only the current assignee or a coordinator can hand over this task.",403)
        cur.execute("INSERT INTO task_handovers(task_id,from_user_id,to_user_id,reason,notes) VALUES(%s,%s,%s,%s,%s)",(task_id,user["id"],target["id"],reason,notes))
        cur.execute("UPDATE tasks SET assigned_to=%s,status='handover' WHERE id=%s",(target["id"],task_id))
        notify(cur,target["id"],"Task handed over",f"{task['task_code']} has been handed over to you.",task_id,"handover")
        audit(cur,user["id"],"task_handed_over","task",task_id,f"To {target['full_name']}; reason: {reason}")
    return jsonify(message="Task handed over.")


@app.post("/api/tasks/<task_id>/comments")
@login_required
def comment(user, task_id):
    text=(request.get_json(silent=True) or {}).get("text","").strip()
    if not text or len(text)>2000: return json_error("Comment must contain 1–2000 characters.")
    with db() as conn, conn.cursor() as cur:
        cur.execute("SELECT id,assigned_to,created_by FROM tasks WHERE id=%s",(task_id,)); t=cur.fetchone()
        if not t: return json_error("Task not found.",404)
        if user["role"] not in {"administrator","coordinator"} and user["id"] not in {t["assigned_to"],t["created_by"]}: return json_error("You do not have access to this task.",403)
        cur.execute("INSERT INTO task_comments(task_id,author_id,body) VALUES(%s,%s,%s)",(task_id,user["id"],text))
        audit(cur,user["id"],"comment_added","task",task_id,"Task comment added")
    return jsonify(message="Comment added."),201


# ---------- Evidence ----------
@app.post("/api/tasks/<task_id>/evidence")
@login_required
def evidence(user, task_id):
    # Supports a real multipart file upload and a safe local file reference for testing.
    description = (request.form.get("description") or request.json.get("description", "") if request.is_json else "").strip() if request.is_json else (request.form.get("description") or "").strip()
    with db() as conn, conn.cursor() as cur:
        cur.execute("SELECT id,assigned_to,created_by,task_code FROM tasks WHERE id=%s",(task_id,)); t=cur.fetchone()
        if not t: return json_error("Task not found.",404)
        if user["role"] not in {"administrator","coordinator"} and user["id"] not in {t["assigned_to"],t["created_by"]}: return json_error("You do not have access to this task.",403)

        filename = None; file_url = None
        uploaded = request.files.get("file")
        if uploaded and uploaded.filename:
            filename = secure_filename(uploaded.filename)
            if not filename: return json_error("Invalid filename.")
            ext = os.path.splitext(filename)[1].lower()
            allowed = {".jpg",".jpeg",".png",".gif",".webp",".pdf",".txt",".doc",".docx",".xls",".xlsx",".csv"}
            if ext not in allowed: return json_error("Unsupported evidence file type.")
            stored = f"{t['task_code']}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}_{filename}"
            uploaded.save(os.path.join(UPLOAD_DIR, stored))
            file_url = f"/uploads/{stored}"
        elif request.is_json:
            data=request.get_json(silent=True) or {}
            filename=(data.get("filename") or "").strip(); file_url=(data.get("fileUrl") or "").strip(); description=(data.get("description") or "").strip()
            if not filename or not file_url: return json_error("Evidence file and description are required.")
        else:
            return json_error("Select an evidence file.")

        cur.execute("INSERT INTO task_evidence(task_id,uploaded_by,filename,file_url,description) VALUES(%s,%s,%s,%s,%s)",(task_id,user["id"],filename,file_url,description))
        cur.execute("UPDATE tasks SET status='for_verification' WHERE id=%s AND assigned_to=%s",(task_id,user["id"]))
        cur.execute("SELECT id FROM users WHERE role='verifier' AND is_active=TRUE")
        for v in cur.fetchall(): notify(cur,v["id"],"Task ready for verification",f"{t['task_code']} has submitted evidence.",task_id,"verification")
        audit(cur,user["id"],"evidence_submitted","task",task_id,filename)
    return jsonify(message="Evidence submitted.", fileUrl=file_url),201


# ---------- Verification ----------
@app.get("/api/verifications")
@login_required
def verifications(user):
    if user["role"] not in {"administrator","coordinator","verifier"}: return json_error("Verifier permission required.",403)
    with db() as conn, conn.cursor() as cur:
        cur.execute(TASK_SELECT + " WHERE t.status IN ('for_verification','verified') ORDER BY t.updated_at DESC")
        rows=cur.fetchall()
    return jsonify(tasks=[task_dict(r) for r in rows])


@app.post("/api/tasks/<task_id>/verify")
@login_required
@roles_required("administrator","coordinator","verifier")
def verify(user, task_id):
    data=request.get_json(silent=True) or {}; decision=(data.get("decision") or "").lower(); remarks=(data.get("remarks") or "").strip()
    if decision not in {"approve","reject"}: return json_error("Decision must be approve or reject.")
    if decision=="reject" and not remarks: return json_error("Remarks are required when rejecting a task.")
    with db() as conn, conn.cursor() as cur:
        cur.execute("SELECT id,task_code,created_by,assigned_to FROM tasks WHERE id=%s",(task_id,)); t=cur.fetchone()
        if not t: return json_error("Task not found.",404)
        status="completed" if decision=="approve" else "rejected"
        cur.execute("INSERT INTO task_verifications(task_id,verifier_id,decision,remarks) VALUES(%s,%s,%s,%s)",(task_id,user["id"],decision,remarks))
        cur.execute("UPDATE tasks SET status=%s WHERE id=%s",(status,task_id))
        notify(cur,t["created_by"],"Task verification updated",f"{t['task_code']} was {'approved' if decision=='approve' else 'rejected'}.",task_id,"verification")
        if t["assigned_to"]: notify(cur,t["assigned_to"],"Task verification updated",f"{t['task_code']} was {'approved' if decision=='approve' else 'rejected'}.",task_id,"verification")
        audit(cur,user["id"],f"task_{decision}d","task",task_id,remarks or "Completion approved")
    return jsonify(message="Verification recorded.")


# ---------- Notifications ----------
@app.get("/api/notifications")
@login_required
def get_notifications(user):
    with db() as conn, conn.cursor() as cur:
        cur.execute("SELECT id,title,message,task_id,kind,is_read,created_at FROM notifications WHERE user_id=%s ORDER BY created_at DESC",(user["id"],)); rows=cur.fetchall()
    return jsonify(notifications=[{**r,"id":str(r["id"]),"task_id":str(r["task_id"]) if r["task_id"] else None} for r in rows])


@app.post("/api/notifications/read")
@login_required
def mark_notifications_read(user):
    with db() as conn, conn.cursor() as cur:
        cur.execute("UPDATE notifications SET is_read=TRUE WHERE user_id=%s",(user["id"],))
    return jsonify(message="Notifications marked as read.")


# ---------- Reports / Audit ----------
@app.get("/api/reports")
@login_required
def reports(user):
    if user["role"] not in {"administrator","coordinator"}: return json_error("Coordinator permission required.",403)
    with db() as conn, conn.cursor() as cur:
        cur.execute("SELECT status,count(*) AS count FROM tasks GROUP BY status ORDER BY count DESC"); by_status=cur.fetchall()
        cur.execute("SELECT priority,count(*) AS count FROM tasks GROUP BY priority ORDER BY count DESC"); by_priority=cur.fetchall()
        cur.execute("SELECT category,count(*) AS count FROM tasks GROUP BY category ORDER BY count DESC LIMIT 10"); by_category=cur.fetchall()
        cur.execute("SELECT u.full_name,count(t.id) AS count FROM users u LEFT JOIN tasks t ON t.assigned_to=u.id WHERE u.role='personnel' GROUP BY u.id,u.full_name ORDER BY count DESC LIMIT 10"); by_personnel=cur.fetchall()
        cur.execute("SELECT count(*) AS total, count(*) FILTER(WHERE status='completed') AS completed, count(*) FILTER(WHERE deadline < now() AND status NOT IN ('completed','cancelled')) AS overdue FROM tasks"); summary=cur.fetchone()
    return jsonify(summary=summary,byStatus=by_status,byPriority=by_priority,byCategory=by_category,byPersonnel=by_personnel)


@app.get("/api/audit-logs")
@login_required
def audit_logs(user):
    if user["role"] not in {"administrator","coordinator"}: return json_error("Administrator/coordinator permission required.",403)
    with db() as conn, conn.cursor() as cur:
        cur.execute("SELECT l.id,l.action,l.entity_type,l.entity_id,l.details,l.created_at,u.full_name AS actor_name FROM audit_logs l LEFT JOIN users u ON u.id=l.actor_id ORDER BY l.created_at DESC LIMIT 200")
        rows=cur.fetchall()
    return jsonify(logs=[{**r,"id":str(r["id"]),"entity_id":str(r["entity_id"]) if r["entity_id"] else None} for r in rows])


# ---------- Activity 2 lab compatibility ----------
@app.get("/lab")
def lab_page():
    return send_from_directory(app.static_folder,"lab_test.html")


@app.get("/api/lab-test/stream")
def lab_test_stream():
    # Preserve the existing localhost-only classroom lab endpoint.
    import json as _json
    import time as _time
    import requests as _requests
    from urllib.parse import urlparse
    target=(request.args.get("target") or "http://127.0.0.1:5000/api/login").strip()
    login_type=(request.args.get("login_type") or "email").strip()
    login_value=(request.args.get("login_value") or "maria@gmail.com").strip()
    parsed=urlparse(target)
    if parsed.hostname not in {"localhost","127.0.0.1","::1"} or parsed.scheme not in {"http","https"}: return json_error("Lab tester only accepts localhost targets.",403)
    if login_type not in {"email","username"}: return json_error("Invalid login type.")
    candidates=["1234","12345","123456","12345678","password","password123","admin","admin123","admin1234","qwerty","welcome","student","student123"]+[f"{i:05d}" for i in range(5001)]
    candidates=list(dict.fromkeys(candidates))
    def generate():
        start=_time.perf_counter(); session_req=_requests.Session()
        yield "TaskChain / Security Lab — localhost controlled test\n"
        yield f"Target: {target}\nIdentifier: {login_value}\nCandidates: {len(candidates)}\n\n"
        try:
            for i,pw in enumerate(candidates,1):
                payload={login_type:login_value,"password":pw}
                try: r=session_req.post(target,json=payload,timeout=5)
                except _requests.RequestException as exc: yield f"[ERROR] {exc}\n"; return
                yield f"[{i:04d}] {pw:<18} HTTP {r.status_code}\n"
                if r.status_code==200:
                    yield f"\nSUCCESS — candidate matched: {pw}\nAttempts: {i}\nElapsed: {_time.perf_counter()-start:.2f}s\n"; return
                if r.status_code==429:
                    yield f"\nDEFENSE DETECTED — blocked after {i} attempts.\nElapsed: {_time.perf_counter()-start:.2f}s\n"; return
                _time.sleep(.01)
            yield f"\nTEST FINISHED — no candidate matched. Attempts: {len(candidates)}\n"
        finally: session_req.close()
    return app.response_class(generate(),mimetype="text/plain",headers={"Cache-Control":"no-store","X-Accel-Buffering":"no"})


if __name__ == "__main__":
    app.run(debug=True)
