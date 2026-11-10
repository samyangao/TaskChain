"""SLA engine and background scheduler (Phase 3), plus auto-close settings."""

import os
import threading
from datetime import datetime, timedelta, timezone
from app.config import DEFAULT_AUTO_CLOSE_DAYS, SLA_LOCK_ID, SLA_OVERDUE_FLIPS, SLA_STOPPED_STATUSES, SLA_WARNING_HOURS
from app.db import db
from app.log import logger
from app.services.audit import audit
from app.services.custody_chain import append_chain_record
from app.services.notification_delivery import _deliver_external, external_channels
from app.services.notifications import notify


# All SLA rules live here. Routes never calculate deadlines or send SLA notices
# themselves; they call apply_task_sla() and the scheduler calls run_sla_check().
def find_category(cur, name, active_only=True):
    cur.execute(
        "SELECT id, name, description, default_sla_hours, escalation_hours, team, is_active "
        "FROM task_categories WHERE lower(name)=lower(%s)" + (" AND is_active=TRUE" if active_only else ""),
        (name,),
    )
    return cur.fetchone()


def compute_sla(start, default_sla_hours, escalation_hours):
    """Pure calculation: due = start + SLA, escalation = due + escalation time."""
    due = start + timedelta(hours=default_sla_hours)
    return {"started_at": start, "due_at": due, "escalate_at": due + timedelta(hours=escalation_hours)}


def apply_task_sla(cur, task_id, start=None):
    """(Re)calculate a task's SLA from its category.

    The clock starts when the request was created (that is when the requester
    starts waiting). Callers that need a fresh clock, such as a future "reopen",
    pass start=now. All warning/overdue/escalation markers are cleared so the
    new deadline is tracked from scratch. A task whose category has no SLA row
    gets no SLA and keeps using the requester's preferred deadline.
    """
    cur.execute("SELECT id, category, created_at FROM tasks WHERE id=%s", (task_id,))
    task = cur.fetchone()
    if not task:
        return None
    category = find_category(cur, task["category"], active_only=False)
    if not category:
        cur.execute(
            """UPDATE tasks SET sla_started_at=NULL, sla_due_at=NULL, sla_escalate_at=NULL,
               sla_warned_at=NULL, sla_overdue_at=NULL, sla_escalated_at=NULL WHERE id=%s""", (task_id,))
        return None
    sla = compute_sla(start or task["created_at"], category["default_sla_hours"], category["escalation_hours"])
    cur.execute(
        """UPDATE tasks SET sla_started_at=%s, sla_due_at=%s, sla_escalate_at=%s,
           sla_warned_at=NULL, sla_overdue_at=NULL, sla_escalated_at=NULL WHERE id=%s""",
        (sla["started_at"], sla["due_at"], sla["escalate_at"], task_id),
    )
    return sla


def sla_state(row, now=None):
    """What the UI should show: none / closed / on_track / due_soon / overdue / escalated."""
    now = now or datetime.now(timezone.utc)
    if row.get("status") in SLA_STOPPED_STATUSES:
        return "closed"
    due = row.get("due_at")
    if due is None:
        return "none"
    if row.get("sla_escalated_at"):
        return "escalated"
    if due <= now:
        return "overdue"
    if due - now <= timedelta(hours=SLA_WARNING_HOURS):
        return "due_soon"
    return "on_track"


def _sla_recipients(cur, assigned_to, roles=("administrator", "coordinator")):
    """The assignee plus every active user in the given roles, each exactly once."""
    ids = []
    if assigned_to:
        ids.append(assigned_to)
    if roles:
        cur.execute("SELECT id FROM users WHERE role = ANY(%s) AND is_active=TRUE", (list(roles),))
        ids.extend(r["id"] for r in cur.fetchall())
    seen, unique = set(), []
    for i in ids:
        if i not in seen:
            seen.add(i); unique.append(i)
    return unique


_SLA_DUE = "COALESCE(sla_due_at, deadline)"  # SLA first, the requester's preferred deadline as fallback


_SLA_WARN = f"""SELECT id, task_code, status, assigned_to, created_by, sla_due_at FROM tasks
    WHERE id=%(id)s AND sla_warned_at IS NULL AND sla_due_at IS NOT NULL AND sla_started_at IS NOT NULL
      AND NOT (status = ANY(%(stopped)s)) AND sla_due_at > %(now)s
      AND sla_due_at - %(now)s <= make_interval(hours => %(warn)s)
      AND sla_due_at - sla_started_at > make_interval(hours => %(warn)s)
    FOR UPDATE SKIP LOCKED"""


_SLA_OVERDUE = f"""SELECT id, task_code, status, assigned_to, created_by, {_SLA_DUE} AS due_at FROM tasks
    WHERE id=%(id)s AND sla_overdue_at IS NULL AND {_SLA_DUE} IS NOT NULL
      AND NOT (status = ANY(%(stopped)s)) AND {_SLA_DUE} <= %(now)s
    FOR UPDATE SKIP LOCKED"""


_SLA_ESCALATE = f"""SELECT id, task_code, status, assigned_to, created_by, sla_due_at, sla_escalate_at FROM tasks
    WHERE id=%(id)s AND sla_escalated_at IS NULL AND sla_escalate_at IS NOT NULL
      AND NOT (status = ANY(%(stopped)s)) AND sla_escalate_at <= %(now)s
    FOR UPDATE SKIP LOCKED"""


_SLA_CANDIDATES = {
    "warned": """SELECT id FROM tasks WHERE sla_warned_at IS NULL AND sla_due_at IS NOT NULL
                 AND NOT (status = ANY(%(stopped)s)) AND sla_due_at > %(now)s
                 AND sla_due_at - %(now)s <= make_interval(hours => %(warn)s) ORDER BY sla_due_at LIMIT 200""",
    "overdue": f"""SELECT id FROM tasks WHERE sla_overdue_at IS NULL AND {_SLA_DUE} IS NOT NULL
                 AND NOT (status = ANY(%(stopped)s)) AND {_SLA_DUE} <= %(now)s ORDER BY {_SLA_DUE} LIMIT 200""",
    "escalated": """SELECT id FROM tasks WHERE sla_escalated_at IS NULL AND sla_escalate_at IS NOT NULL
                 AND NOT (status = ANY(%(stopped)s)) AND sla_escalate_at <= %(now)s ORDER BY sla_escalate_at LIMIT 200""",
    "auto_closed": """SELECT id FROM tasks WHERE status='completed' AND confirmed_at IS NULL AND completed_at IS NOT NULL
                 AND completed_at <= %(now)s - make_interval(days => %(close_days)s) ORDER BY completed_at LIMIT 200""",
}


def _sla_warn(cur, task_id, params, outbox):
    cur.execute(_SLA_WARN, {**params, "id": task_id})
    t = cur.fetchone()
    if not t:
        return False  # not due for a warning, or another process already claimed it
    cur.execute("UPDATE tasks SET sla_warned_at=%s WHERE id=%s", (params["now"], t["id"]))
    msg = f"{t['task_code']} is due within {SLA_WARNING_HOURS} hours."
    # The person doing the work; if nobody has it yet, the people who can assign it.
    recipients = _sla_recipients(cur, None, ("administrator", "coordinator")) if not t["assigned_to"] else [t["assigned_to"]]
    for uid_ in recipients:
        notify(cur, uid_, f"Due in {SLA_WARNING_HOURS} hours", msg, t["id"], "sla", outbox=outbox)
    return True


def _sla_overdue(cur, task_id, params, outbox):
    cur.execute(_SLA_OVERDUE, {**params, "id": task_id})
    t = cur.fetchone()
    if not t:
        return False
    new_status = "overdue" if t["status"] in SLA_OVERDUE_FLIPS else t["status"]
    cur.execute("UPDATE tasks SET sla_overdue_at=%s, status=%s WHERE id=%s", (params["now"], new_status, t["id"]))
    audit(cur, None, "task_overdue", "task", t["id"], f"{t['task_code']} passed its deadline ({t['due_at'].isoformat()})")
    append_chain_record(cur, t["id"], "task_overdue", None, {
        "from_status": t["status"], "to_status": new_status, "due_at": t["due_at"].isoformat(),
    })
    msg = f"{t['task_code']} has passed its SLA deadline."
    for uid_ in _sla_recipients(cur, t["assigned_to"]):
        notify(cur, uid_, "Task overdue", msg, t["id"], "sla", outbox=outbox)
    return True


def _sla_escalate(cur, task_id, params, outbox):
    cur.execute(_SLA_ESCALATE, {**params, "id": task_id})
    t = cur.fetchone()
    if not t:
        return False
    cur.execute("UPDATE tasks SET sla_escalated_at=%s WHERE id=%s", (params["now"], t["id"]))
    hours = max(0, int((params["now"] - t["sla_due_at"]).total_seconds() // 3600))
    audit(cur, None, "task_escalated", "task", t["id"], f"{t['task_code']} escalated to coordinators ({hours}h past its SLA deadline)")
    append_chain_record(cur, t["id"], "task_escalated", None, {
        "due_at": t["sla_due_at"].isoformat(), "escalate_at": t["sla_escalate_at"].isoformat(), "hours_past_due": hours,
    })
    msg = f"{t['task_code']} is still unresolved {hours} hour(s) after its SLA deadline and needs attention."
    for uid_ in _sla_recipients(cur, None):
        notify(cur, uid_, "Task escalated", msg, t["id"], "sla", outbox=outbox)
    return True


_AUTOCLOSE = """SELECT id, task_code, created_by, assigned_to, completed_at FROM tasks
    WHERE id=%(id)s AND status='completed' AND confirmed_at IS NULL AND completed_at IS NOT NULL
      AND completed_at <= %(now)s - make_interval(days => %(close_days)s)
    FOR UPDATE SKIP LOCKED"""


def _sla_autoclose(cur, task_id, params, outbox):
    """A completed request the requester never answered closes itself after N days."""
    cur.execute(_AUTOCLOSE, {**params, "id": task_id})
    t = cur.fetchone()
    if not t:
        return False
    cur.execute("UPDATE tasks SET confirmed_at=%s, confirmation_type='auto' WHERE id=%s", (params["now"], t["id"]))
    days = params["close_days"]
    audit(cur, None, "task_auto_closed", "task", t["id"], f"{t['task_code']} closed automatically: not confirmed within {days} day(s)")
    append_chain_record(cur, t["id"], "task_auto_closed", None, {
        "completed_at": t["completed_at"].isoformat(), "closed_after_days": days,
    })
    notify(cur, t["created_by"], "Request closed automatically",
           f"{t['task_code']} was closed because it was not confirmed within {days} day(s). You can still rate it.",
           t["id"], "task", outbox=outbox)
    return True


_SLA_STAGES = (("warned", _sla_warn), ("overdue", _sla_overdue), ("escalated", _sla_escalate), ("auto_closed", _sla_autoclose))


def run_sla_check(now=None):
    """One pass of the SLA engine. Safe to call at any time and from several processes.

    Order matters: warn, then overdue, then escalate. Every action claims the task
    with SELECT ... FOR UPDATE SKIP LOCKED, stamps its marker and sends its
    notification in ONE transaction, so a task is warned / flagged / escalated at
    most once no matter how often this runs. One task failing never blocks others.
    """
    now = now or datetime.now(timezone.utc)
    counts = {"warned": 0, "overdue": 0, "escalated": 0, "auto_closed": 0}
    params = {"now": now, "stopped": list(SLA_STOPPED_STATUSES), "warn": SLA_WARNING_HOURS, "close_days": 0}
    outbox = []
    with db() as conn:
        conn.autocommit = True  # so conn.transaction() below is a real, per-task transaction
        with conn.cursor() as cur:
            cur.execute("SELECT pg_try_advisory_lock(%s) AS got", (SLA_LOCK_ID,))
            if not cur.fetchone()["got"]:
                return {**counts, "skipped": True}  # another process is already running a check
            params["close_days"] = get_auto_close_days(cur)
        for stage, handler in _SLA_STAGES:
            if stage == "auto_closed" and params["close_days"] <= 0:
                continue  # auto-close is switched off (0 days)
            with conn.cursor() as cur:
                cur.execute(_SLA_CANDIDATES[stage], params)
                ids = [r["id"] for r in cur.fetchall()]
            for task_id in ids:
                try:
                    with conn.transaction(), conn.cursor() as cur:
                        if handler(cur, task_id, params, outbox):
                            counts[stage] += 1
                except Exception as exc:
                    logger.warning("SLA %s step failed for one task: %s", stage, type(exc).__name__)
    if outbox and any(external_channels().values()):
        _deliver_external(outbox)  # runs after the transactions above have committed
    return counts


_sla_stop = threading.Event()


def _sla_loop(interval):
    while True:
        try:
            counts = run_sla_check()
            if any(counts.get(k) for k in ("warned", "overdue", "escalated", "auto_closed")):
                logger.info("SLA check: %s", counts)
        except Exception as exc:
            logger.warning("SLA check failed: %s", type(exc).__name__)
        if _sla_stop.wait(interval):
            return


def start_sla_scheduler():
    """Simple local scheduler: one daemon thread, one check every SLA_CHECK_SECONDS (default 60).

    No cloud service needed. Set SLA_SCHEDULER=0 to switch it off. If it dies the app still
    works; POST /api/sla/run (administrator) runs a check by hand.
    """
    if os.environ.get("SLA_SCHEDULER", "1") == "0":
        return None
    try:
        interval = max(10, int(os.environ.get("SLA_CHECK_SECONDS", "60")))
    except ValueError:
        interval = 60
    thread = threading.Thread(target=_sla_loop, args=(interval,), name="sla-scheduler", daemon=True)
    thread.start()
    return thread


def get_auto_close_days(cur):
    cur.execute("SELECT value FROM app_settings WHERE key='auto_close_days'")
    row = cur.fetchone()
    try:
        return min(max(int(row["value"]), 0), 365) if row else DEFAULT_AUTO_CLOSE_DAYS
    except (TypeError, ValueError):
        return DEFAULT_AUTO_CLOSE_DAYS
