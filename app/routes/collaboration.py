"""Comments, watchers, subtasks and dependencies (Phase 7)."""

from collections import defaultdict
from flask import Blueprint, jsonify, request
from app.db import db
from app.permissions import can_view_task, is_manager, login_required
from app.services.audit import audit
from app.services.collaboration import DEPENDENCY_REQUIRED_STATES, can_edit_collaboration, dependency_met, notify_task_watchers, watch_task
from app.services.custody_chain import append_chain_record
from app.services.notifications import notify
from app.utils import _short, json_error, parse_uuid

bp = Blueprint("collaboration", __name__)


@bp.post("/api/tasks/<task_id>/comments")
@login_required
def comment(user, task_id):
    if not parse_uuid(task_id): return json_error("Invalid task id.", 400)
    data = request.get_json(silent=True) or {}
    text = str(data.get("text") or "").strip()
    if not text or len(text) > 2000: return json_error("Comment must contain 1–2000 characters.")
    raw_mentions = data.get("mentions") or []
    if not isinstance(raw_mentions, list):
        raw_mentions = []
    mention_ids = []
    for value in raw_mentions[:20]:
        uid = parse_uuid(value)
        if uid and str(uid) not in mention_ids:
            mention_ids.append(str(uid))
    with db() as conn, conn.cursor() as cur:
        cur.execute("SELECT id,task_code,assigned_to,created_by FROM tasks WHERE id=%s",(task_id,)); t=cur.fetchone()
        if not t: return json_error("Task not found.",404)
        if not can_view_task(user, t): return json_error("You do not have access to this task.",403)
        cur.execute("SELECT user_id FROM task_watchers WHERE task_id=%s", (task_id,))
        watcher_ids = {str(r["user_id"]) for r in cur.fetchall()}
        mentioned = []
        participants = {str(t["created_by"])}
        if t["assigned_to"]:
            participants.add(str(t["assigned_to"]))
        if mention_ids:
            cur.execute("SELECT id,full_name,role FROM users WHERE id=ANY(%s) AND is_active=TRUE", (mention_ids,))
            allowed = participants | watcher_ids
            mentioned = [
                r for r in cur.fetchall()
                if r["role"] in {"administrator", "coordinator"} or str(r["id"]) in allowed
            ]
        cur.execute("INSERT INTO task_comments(task_id,author_id,body) VALUES(%s,%s,%s) RETURNING id,created_at",
                    (task_id, user["id"], text))
        created = cur.fetchone()
        for mention in mentioned:
            cur.execute("INSERT INTO task_comment_mentions(comment_id,user_id) VALUES(%s,%s) ON CONFLICT DO NOTHING",
                        (created["id"], mention["id"]))
        watch_task(cur, task_id, user["id"])
        code = t["task_code"]
        mentioned_ids = {str(r["id"]) for r in mentioned}
        for mention in mentioned:
            notify(cur, mention["id"], f"You were mentioned in {code}",
                   f"{user['full_name']}: {_short(text, 140)}", task_id, "mention", actor_id=user["id"])
        others = (participants | watcher_ids) - mentioned_ids - {str(user["id"])}
        for recipient in others:
            if recipient:
                notify(cur, recipient, f"New comment on {code}",
                       f"{user['full_name']}: {_short(text, 140)}", task_id, "comment", actor_id=user["id"])
        audit(cur,user["id"],"comment_added","task",task_id,
              f"Task comment added" + (f" mentioning {len(mentioned)}" if mentioned else ""))
        append_chain_record(cur, task_id, "comment_added", user["id"], {
            "comment": text, "mentions": [r["full_name"] for r in mentioned],
        })
    return jsonify(message="Comment added.", commentId=str(created["id"])),201


@bp.post("/api/tasks/<task_id>/watch")
@login_required
def toggle_watch(user, task_id):
    if not parse_uuid(task_id): return json_error("Invalid task id.", 400)
    with db() as conn, conn.cursor() as cur:
        cur.execute("SELECT id,task_code,created_by,assigned_to FROM tasks WHERE id=%s", (task_id,))
        task = cur.fetchone()
        if not task: return json_error("Task not found.", 404)
        if not can_view_task(user, task): return json_error("You do not have access to this task.", 403)
        cur.execute("SELECT 1 FROM task_watchers WHERE task_id=%s AND user_id=%s", (task_id, user["id"]))
        if cur.fetchone():
            cur.execute("DELETE FROM task_watchers WHERE task_id=%s AND user_id=%s", (task_id, user["id"]))
            watching = False
            message = "You are no longer watching this task."
        else:
            watch_task(cur, task_id, user["id"])
            watching = True
            message = "You are now watching this task."
        cur.execute("SELECT count(*) AS n FROM task_watchers WHERE task_id=%s", (task_id,))
        count = cur.fetchone()["n"]
    return jsonify(message=message, watching=watching, watcherCount=count)


@bp.post("/api/tasks/<task_id>/subtasks")
@login_required
def add_subtask(user, task_id):
    if not parse_uuid(task_id): return json_error("Invalid task id.", 400)
    data = request.get_json(silent=True) or {}
    title = " ".join(str(data.get("title") or "").split())
    if not title or len(title) > 160:
        return json_error("Enter a subtask title of up to 160 characters.")
    with db() as conn, conn.cursor() as cur:
        cur.execute("SELECT id,task_code,created_by,assigned_to FROM tasks WHERE id=%s", (task_id,))
        task = cur.fetchone()
        if not task: return json_error("Task not found.", 404)
        if not can_edit_collaboration(user, task):
            return json_error("You do not have permission to edit this task's checklist.", 403)
        cur.execute("SELECT COALESCE(max(position),-1)+1 AS position FROM task_subtasks WHERE task_id=%s", (task_id,))
        position = cur.fetchone()["position"]
        cur.execute(
            """INSERT INTO task_subtasks(task_id,title,position,created_by)
               VALUES(%s,%s,%s,%s) RETURNING id,title,position,is_done,created_at""",
            (task_id, title, position, user["id"]),
        )
        row = cur.fetchone()
        watch_task(cur, task_id, user["id"])
        audit(cur, user["id"], "subtask_added", "task", task_id, title)
        append_chain_record(cur, task_id, "subtask_added", user["id"], {"title": title})
        notify_task_watchers(cur, task_id, "Subtask added", f"{task['task_code']}: {title}",
                             user["id"], "subtask", exclude={task["created_by"], task["assigned_to"]})
    return jsonify(message="Subtask added.", subtask={**row, "id": str(row["id"])}), 201


@bp.patch("/api/tasks/<task_id>/subtasks/<subtask_id>")
@login_required
def update_subtask(user, task_id, subtask_id):
    if not parse_uuid(task_id) or not parse_uuid(subtask_id):
        return json_error("Invalid identifier.", 400)
    data = request.get_json(silent=True) or {}
    with db() as conn, conn.cursor() as cur:
        cur.execute("SELECT id,task_code,created_by,assigned_to FROM tasks WHERE id=%s", (task_id,))
        task = cur.fetchone()
        if not task: return json_error("Task not found.", 404)
        if not can_edit_collaboration(user, task):
            return json_error("You do not have permission to edit this checklist.", 403)
        cur.execute("SELECT id,title,is_done FROM task_subtasks WHERE id=%s AND task_id=%s FOR UPDATE",
                    (subtask_id, task_id))
        subtask = cur.fetchone()
        if not subtask: return json_error("Subtask not found.", 404)
        event = None
        if "title" in data:
            title = " ".join(str(data.get("title") or "").split())
            if not title or len(title) > 160:
                return json_error("Enter a subtask title of up to 160 characters.")
            cur.execute("UPDATE task_subtasks SET title=%s WHERE id=%s", (title, subtask_id))
            event = "subtask_updated"
        if "isDone" in data:
            if not isinstance(data["isDone"], bool):
                return json_error("isDone must be true or false.")
            if data["isDone"] != subtask["is_done"]:
                if data["isDone"]:
                    cur.execute("UPDATE task_subtasks SET is_done=TRUE, done_at=now(), done_by=%s WHERE id=%s",
                                (user["id"], subtask_id))
                    event = "subtask_completed"
                else:
                    cur.execute("UPDATE task_subtasks SET is_done=FALSE, done_at=NULL, done_by=NULL WHERE id=%s",
                                (subtask_id,))
                    event = "subtask_reopened"
        if not event:
            return json_error("No valid changes supplied.")
        cur.execute("SELECT count(*) AS total, count(*) FILTER (WHERE is_done) AS done FROM task_subtasks WHERE task_id=%s",
                    (task_id,))
        counts = cur.fetchone()
        audit(cur, user["id"], event, "task", task_id, subtask["title"])
        append_chain_record(cur, task_id, event, user["id"], {"title": subtask["title"]})
        if event in {"subtask_completed", "subtask_reopened"}:
            notify_task_watchers(
                cur, task_id, "Checklist updated",
                f"{task['task_code']}: {subtask['title']} was {'completed' if event == 'subtask_completed' else 'reopened'} ({counts['done']}/{counts['total']}).",
                user["id"], "subtask", exclude={task["created_by"], task["assigned_to"]},
            )
    return jsonify(message="Subtask updated.", done=counts["done"], total=counts["total"])


@bp.delete("/api/tasks/<task_id>/subtasks/<subtask_id>")
@login_required
def delete_subtask(user, task_id, subtask_id):
    if not parse_uuid(task_id) or not parse_uuid(subtask_id):
        return json_error("Invalid identifier.", 400)
    with db() as conn, conn.cursor() as cur:
        cur.execute("SELECT id,task_code,created_by,assigned_to FROM tasks WHERE id=%s", (task_id,))
        task = cur.fetchone()
        if not task: return json_error("Task not found.", 404)
        if not can_edit_collaboration(user, task):
            return json_error("You do not have permission to edit this checklist.", 403)
        cur.execute("DELETE FROM task_subtasks WHERE id=%s AND task_id=%s RETURNING title", (subtask_id, task_id))
        row = cur.fetchone()
        if not row: return json_error("Subtask not found.", 404)
        audit(cur, user["id"], "subtask_deleted", "task", task_id, row["title"])
        append_chain_record(cur, task_id, "subtask_deleted", user["id"], {"title": row["title"]})
    return jsonify(message="Subtask removed.")


@bp.get("/api/tasks/<task_id>/dependency-options")
@login_required
def dependency_options(user, task_id):
    if not parse_uuid(task_id): return json_error("Invalid task id.", 400)
    with db() as conn, conn.cursor() as cur:
        cur.execute("SELECT id,task_code,created_by,assigned_to FROM tasks WHERE id=%s", (task_id,))
        task = cur.fetchone()
        if not task: return json_error("Task not found.", 404)
        if not can_view_task(user, task): return json_error("You do not have access to this task.", 403)
        if is_manager(user):
            cur.execute(
                """SELECT id,task_code,title,status FROM tasks WHERE id<>%s
                   ORDER BY updated_at DESC LIMIT 300""", (task_id,))
        else:
            cur.execute(
                """SELECT id,task_code,title,status FROM tasks
                   WHERE id<>%s AND (created_by=%s OR assigned_to=%s)
                   ORDER BY updated_at DESC LIMIT 300""", (task_id, user["id"], user["id"]))
        candidates = cur.fetchall()
        cur.execute("SELECT depends_on_id FROM task_dependencies WHERE task_id=%s", (task_id,))
        existing = {str(r["depends_on_id"]) for r in cur.fetchall()}
        cur.execute("SELECT task_id,depends_on_id FROM task_dependencies")
        adjacency = defaultdict(set)
        for edge in cur.fetchall():
            adjacency[str(edge["task_id"])].add(str(edge["depends_on_id"]))

    def reaches(start, target, seen=None):
        seen = seen or set()
        if start == target:
            return True
        if start in seen:
            return False
        seen.add(start)
        return any(reaches(nxt, target, seen) for nxt in adjacency.get(start, ()))

    options = []
    for candidate in candidates:
        cid = str(candidate["id"])
        if cid in existing:
            continue
        # If candidate already depends (directly or indirectly) on this task,
        # adding this task -> candidate would create a cycle.
        if reaches(cid, str(task["id"])):
            continue
        options.append({**candidate, "id": cid})
    return jsonify(options=options)


@bp.post("/api/tasks/<task_id>/dependencies")
@login_required
def add_dependency(user, task_id):
    if not parse_uuid(task_id): return json_error("Invalid task id.", 400)
    data = request.get_json(silent=True) or {}
    depends_on_id = parse_uuid(data.get("dependsOnId"))
    required_state = str(data.get("requiredState") or "completed").strip().lower()
    if not depends_on_id: return json_error("Choose the task that must finish first.")
    if required_state not in DEPENDENCY_REQUIRED_STATES:
        return json_error("Required state must be 'for_verification' or 'completed'.")
    if str(depends_on_id) == str(task_id):
        return json_error("A task cannot depend on itself.")
    with db() as conn, conn.cursor() as cur:
        cur.execute("SELECT id,task_code,created_by,assigned_to FROM tasks WHERE id=%s", (task_id,))
        task = cur.fetchone()
        if not task: return json_error("Task not found.", 404)
        if not can_edit_collaboration(user, task):
            return json_error("You do not have permission to add dependencies to this task.", 403)
        cur.execute("SELECT id,task_code,title,status,created_by,assigned_to FROM tasks WHERE id=%s", (depends_on_id,))
        blocker = cur.fetchone()
        if not blocker: return json_error("The task to depend on was not found.", 404)
        if not can_view_task(user, blocker): return json_error("You do not have access to that task.", 403)
        cur.execute(
            """WITH RECURSIVE reach(dep) AS (
                   SELECT depends_on_id FROM task_dependencies WHERE task_id=%s
                   UNION
                   SELECT d.depends_on_id FROM task_dependencies d JOIN reach r ON d.task_id=r.dep
               )
               SELECT 1 FROM reach WHERE dep=%s LIMIT 1""",
            (depends_on_id, task_id),
        )
        if cur.fetchone():
            return json_error("That dependency would create a cycle.", 409)
        met = dependency_met(required_state, blocker["status"])
        cur.execute(
            """INSERT INTO task_dependencies(task_id,depends_on_id,required_state,created_by,released_at)
               VALUES(%s,%s,%s,%s,CASE WHEN %s THEN now() ELSE NULL END)
               ON CONFLICT (task_id,depends_on_id) DO UPDATE
               SET required_state=EXCLUDED.required_state, released_at=EXCLUDED.released_at""",
            (task_id, depends_on_id, required_state, user["id"], met),
        )
        audit(cur, user["id"], "dependency_added", "task", task_id,
              f"{task['task_code']} depends on {blocker['task_code']} ({required_state})")
        append_chain_record(cur, task_id, "dependency_added", user["id"], {
            "depends_on": blocker["task_code"], "required_state": required_state,
        })
        notify(cur, task["created_by"], "Dependency added",
               f"{task['task_code']} now waits for {blocker['task_code']} ({required_state.replace('_',' ')}).",
               task_id, "dependency", actor_id=user["id"])
        if task["assigned_to"]:
            notify(cur, task["assigned_to"], "Dependency added",
                   f"{task['task_code']} now waits for {blocker['task_code']} ({required_state.replace('_',' ')}).",
                   task_id, "dependency", actor_id=user["id"])
        notify_task_watchers(cur, task_id, "Dependency added",
                             f"{task['task_code']} now waits for {blocker['task_code']}.",
                             user["id"], "dependency", exclude={task["created_by"], task["assigned_to"]})
    return jsonify(message="Dependency added.", met=met)


@bp.delete("/api/tasks/<task_id>/dependencies/<depends_on_id>")
@login_required
def delete_dependency(user, task_id, depends_on_id):
    if not parse_uuid(task_id) or not parse_uuid(depends_on_id):
        return json_error("Invalid identifier.", 400)
    with db() as conn, conn.cursor() as cur:
        cur.execute("SELECT id,task_code,created_by,assigned_to FROM tasks WHERE id=%s", (task_id,))
        task = cur.fetchone()
        if not task: return json_error("Task not found.", 404)
        if not can_edit_collaboration(user, task):
            return json_error("You do not have permission to change this task's dependencies.", 403)
        cur.execute("DELETE FROM task_dependencies WHERE task_id=%s AND depends_on_id=%s RETURNING required_state",
                    (task_id, depends_on_id))
        row = cur.fetchone()
        if not row: return json_error("Dependency not found.", 404)
        cur.execute("SELECT task_code FROM tasks WHERE id=%s", (depends_on_id,))
        blocker = cur.fetchone()
        audit(cur, user["id"], "dependency_removed", "task", task_id,
              f"Dependency on {blocker['task_code'] if blocker else depends_on_id} removed")
        append_chain_record(cur, task_id, "dependency_removed", user["id"], {
            "depends_on": blocker["task_code"] if blocker else str(depends_on_id),
        })
    return jsonify(message="Dependency removed.")
