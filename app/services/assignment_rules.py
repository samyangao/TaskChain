"""Smarter assignment helpers: options, workload, assign and accept logic (Phase 4)."""

from flask import jsonify
from app.services.audit import audit
from app.services.collaboration import blocking_message, notify_task_watchers
from app.services.custody_chain import append_chain_record
from app.services.handovers import _checklist_summary, custody_close, custody_open
from app.services.notifications import notify
from app.services.sla_engine import find_category
from app.utils import _short, json_error


# Workload = tasks a person currently has to work on. for_verification is not counted
# (their part is done, a verifier has it) and neither are closed tasks.
WORKLOAD_ACTIVE_STATUSES = ("assigned", "accepted", "in_progress", "waiting", "handover", "overdue", "rejected")


ASSIGNABLE_ROLES = ("personnel", "coordinator", "administrator")


ACCEPTABLE_STATUSES = ("assigned", "overdue", "handover")  # states in which the holder has not started yet


def _clean_reason(value, limit=500):
    text = " ".join(str(value or "").split())
    return text if 0 < len(text) <= limit else None


def known_teams(cur):
    """Team names in use by categories, keyed by lower-case name (so matching ignores case)."""
    cur.execute("SELECT DISTINCT team FROM task_categories WHERE btrim(team) <> '' ORDER BY team")
    teams = {}
    for r in cur.fetchall():
        teams.setdefault(r["team"].lower(), r["team"])
    return teams


def workload_counts(cur, user_ids):
    """Active task count per user, calculated on the server from the tasks table."""
    if not user_ids:
        return {}
    cur.execute(
        "SELECT assigned_to, count(*) AS n FROM tasks WHERE assigned_to = ANY(%s) AND status = ANY(%s) GROUP BY assigned_to",
        (list(user_ids), list(WORKLOAD_ACTIVE_STATUSES)),
    )
    return {r["assigned_to"]: r["n"] for r in cur.fetchall()}


def assignment_options(cur, task):
    """Who could take this task, how busy they are, and who we suggest.

    Eligible = active personnel account, member of the category's team (any team if the
    category names none), not the current holder, and not someone who already declined
    this task. The suggestion is the eligible person with the fewest active tasks
    (ties broken by name so the answer is stable). Coordinators/administrators are listed
    as manual overrides but are never suggested.
    """
    category = find_category(cur, task["category"], active_only=False)
    team = (category["team"] if category else "").strip()
    cur.execute("SELECT id, full_name, role FROM users WHERE is_active=TRUE AND role = ANY(%s) ORDER BY full_name", (list(ASSIGNABLE_ROLES),))
    people = cur.fetchall()
    ids = [p["id"] for p in people]
    membership = {}
    if ids:
        cur.execute("SELECT user_id, team FROM user_teams WHERE user_id = ANY(%s)", (ids,))
        for r in cur.fetchall():
            membership.setdefault(r["user_id"], []).append(r["team"])
    cur.execute("SELECT DISTINCT actor_id FROM task_assignment_history WHERE task_id=%s AND event='declined'", (task["id"],))
    declined = {r["actor_id"] for r in cur.fetchall()}
    loads = workload_counts(cur, ids)
    options = []
    for p in people:
        teams = membership.get(p["id"], [])
        if not team:
            compatibility = "no_team_required"
        elif any(t.lower() == team.lower() for t in teams):
            compatibility = "match"
        else:
            compatibility = "different_team"
        note = ""
        if p["id"] == task["assigned_to"]: note = "Current holder"
        elif p["role"] != "personnel": note = "Not a personnel account (manual override)"
        elif compatibility == "different_team": note = f"Not in team {team}"
        elif p["id"] in declined: note = "Declined this task earlier"
        eligible = p["role"] == "personnel" and compatibility != "different_team" and not note
        options.append({
            "id": str(p["id"]), "full_name": p["full_name"], "role": p["role"], "teams": teams,
            "active_tasks": loads.get(p["id"], 0), "compatibility": compatibility,
            "eligible": eligible, "suggested": False, "note": note,
        })
    options.sort(key=lambda o: (not o["eligible"], o["active_tasks"] if o["eligible"] else 0, o["full_name"].lower()))
    suggestion = next((o for o in options if o["eligible"]), None)
    if suggestion:
        suggestion["suggested"] = True
    overall = ""
    if not suggestion:
        overall = (f"No available personnel belong to team {team}. Add members under Users, or choose someone manually."
                   if team else "No available personnel account to suggest.")
    return {"team": team, "options": options, "suggested_user_id": suggestion["id"] if suggestion else None, "note": overall}


def _task_for_assignment(cur, task_id):
    cur.execute("SELECT id,task_code,status,assigned_to,created_by,category,accepted_at FROM tasks WHERE id=%s FOR UPDATE", (task_id,))
    return cur.fetchone()


def _assignee_account(cur, user_id):
    cur.execute("SELECT id,full_name,role FROM users WHERE id=%s AND is_active=TRUE", (user_id,))
    return cur.fetchone()


def _assign_task(cur, actor, task, target, event, reason=""):
    """The one place a task changes hands by coordinator action (event: 'assigned' or 'reassigned').

    Writes the task, the assignment history, the audit log, the custody chain and the
    notifications together, inside the caller's transaction.
    """
    previous = task["assigned_to"]
    previous_name = None
    if previous:
        cur.execute("SELECT full_name FROM users WHERE id=%s", (previous,))
        previous_name = cur.fetchone()["full_name"]
    cur.execute("UPDATE tasks SET assigned_to=%s, status='assigned', accepted_at=NULL WHERE id=%s", (target["id"], task["id"]))
    custody_close(cur, task["id"], "reassigned")  # the previous holder's custody ends when the coordinator moves the task
    cur.execute("UPDATE task_handovers SET outcome='superseded', resolved_at=now() WHERE task_id=%s AND outcome='pending'", (task["id"],))
    cur.execute(
        "INSERT INTO task_assignment_history(task_id,event,from_user_id,to_user_id,actor_id,reason) VALUES (%s,%s,%s,%s,%s,%s)",
        (task["id"], event, previous, target["id"], actor["id"], reason),
    )
    code = task["task_code"]
    audit(cur, actor["id"], f"task_{event}", "task", task["id"],
          f"{event.capitalize()} to {target['full_name']}" + (f" (from {previous_name})" if previous_name else "") + (f": {reason}" if reason else ""))
    chain_data = {"assigned_to": str(target["id"]), "assigned_to_name": target["full_name"]}
    if event == "reassigned":
        chain_data.update({"previous_assignee": str(previous), "previous_assignee_name": previous_name, "reason": reason})
    append_chain_record(cur, task["id"], f"task_{event}", actor["id"], chain_data)
    tail = f": {_short(reason)}" if reason else "."
    notify(cur, target["id"], f"Task {event}", f"You have been {event} {code}" + (tail if reason else "."), task["id"], "assignment", actor_id=actor["id"])
    if event == "reassigned":
        notify(cur, previous, "Task reassigned", f"{code} was reassigned to {target['full_name']}" + (tail if reason else "."), task["id"], "assignment", actor_id=actor["id"])
    if task["created_by"] != target["id"]:
        notify(cur, task["created_by"], f"Task {event}", f"{code} was {event} to {target['full_name']}.", task["id"], "assignment", actor_id=actor["id"])


def accept_assignment(cur, user, task_id, require_handover=False):
    """Accept a task, or acknowledge a handover that is waiting for this person.

    Used by POST /accept, POST /handover/acknowledge and PATCH status=accepted, so all three behave
    identically. Custody of the task starts here: when the holder accepts it, or when the receiver
    acknowledges a handover (which is also when the sender's custody ends).
    """
    task = _task_for_assignment(cur, task_id)
    if not task: return json_error("Task not found.", 404)
    if task["assigned_to"] != user["id"]:
        return json_error("Only the person this task is assigned to can accept it.", 403)
    cur.execute("SELECT id, from_user_id FROM task_handovers WHERE task_id=%s AND to_user_id=%s AND outcome='pending' "
                "ORDER BY created_at DESC LIMIT 1 FOR UPDATE", (task["id"], user["id"]))
    handover = cur.fetchone()
    if require_handover and not handover:
        return json_error("There is no handover waiting for your acknowledgment.", 409)
    if task["accepted_at"] is not None or task["status"] not in ACCEPTABLE_STATUSES:
        return json_error("This task cannot be accepted in its current state.", 409)
    block = blocking_message(cur, task["id"])
    if block:
        return json_error(block, 409)
    if handover:
        return _acknowledge_handover(cur, user, task, handover)
    cur.execute("UPDATE tasks SET status='accepted', accepted_at=now() WHERE id=%s", (task["id"],))
    custody_open(cur, task["id"], user["id"], "accepted")
    cur.execute("INSERT INTO task_assignment_history(task_id,event,from_user_id,to_user_id,actor_id) VALUES (%s,'accepted',%s,%s,%s)",
                (task["id"], user["id"], user["id"], user["id"]))
    audit(cur, user["id"], "task_accepted", "task", task["id"], f"Accepted by {user['full_name']}")
    append_chain_record(cur, task["id"], "task_accepted", user["id"], {
        "accepted_by": str(user["id"]), "accepted_by_name": user["full_name"], "from_status": task["status"],
    })
    notify(cur, task["created_by"], "Task accepted", f"{task['task_code']} was accepted by {user['full_name']}.", task["id"], "task", actor_id=user["id"])
    notify_task_watchers(cur, task["id"], "Task accepted", f"{task['task_code']} was accepted by {user['full_name']}.",
                         user["id"], "task", exclude={task["created_by"], user["id"]})
    return jsonify(message="Task accepted.")


def _acknowledge_handover(cur, user, task, handover):
    cur.execute("SELECT full_name FROM users WHERE id=%s", (handover["from_user_id"],))
    sender = cur.fetchone()
    cur.execute("SELECT label, state FROM task_handover_items WHERE handover_id=%s ORDER BY position", (handover["id"],))
    summary = _checklist_summary(cur.fetchall())
    cur.execute("UPDATE task_handovers SET outcome='acknowledged', resolved_at=now() WHERE id=%s", (handover["id"],))
    cur.execute("UPDATE tasks SET status='accepted', accepted_at=now() WHERE id=%s", (task["id"],))
    custody_close(cur, task["id"], "handed_over")          # the sender's custody ends ...
    custody_open(cur, task["id"], user["id"], "acknowledged")  # ... and the receiver's begins, at the same moment
    cur.execute("INSERT INTO task_assignment_history(task_id,event,from_user_id,to_user_id,actor_id) VALUES (%s,'accepted',%s,%s,%s)",
                (task["id"], handover["from_user_id"], user["id"], user["id"]))
    audit(cur, user["id"], "handover_acknowledged", "task", task["id"], f"Handover from {sender['full_name']} acknowledged by {user['full_name']}")
    append_chain_record(cur, task["id"], "handover_acknowledged", user["id"], {
        "handover_id": str(handover["id"]), "from_user": str(handover["from_user_id"]), "from_name": sender["full_name"],
        "to_user": str(user["id"]), "to_name": user["full_name"], "checklist": summary, "from_status": task["status"],
    })
    code = task["task_code"]
    notify(cur, handover["from_user_id"], "Handover acknowledged", f"{user['full_name']} acknowledged the handover of {code}.", task["id"], "handover", actor_id=user["id"])
    if task["created_by"] not in (user["id"], handover["from_user_id"]):
        notify(cur, task["created_by"], "Handover completed", f"{code} was handed over from {sender['full_name']} to {user['full_name']}.", task["id"], "handover", actor_id=user["id"])
    return jsonify(message="Handover acknowledged. The task is now in your custody.")
