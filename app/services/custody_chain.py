"""Tamper-evident custody chain: hashing, appending and verifying records (Phase 1)."""

import hashlib
import json
from datetime import datetime, timezone
from app.db import db


# The genesis value is a fixed, well-known constant. Every chain starts here
# so that the first record is deterministic and verifiable.
GENESIS_HASH = "TASKCHAIN_CUSTODY_GENESIS_v1"


def canonicalize(obj):
    """Deterministic JSON serialization: sorted keys, compact separators."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def compute_chain_hash(previous_hash, event_content):
    """SHA-256 of (previous_hash + canonicalized event content).

    The hash is deterministic: the same inputs always produce the same output.
    No random or time-based values are mixed into the hash itself.
    """
    canonical = canonicalize(event_content)
    return hashlib.sha256((previous_hash + canonical).encode("utf-8")).hexdigest()


def _utc_iso(value):
    """Canonical timestamp text used for hashing.

    PostgreSQL hands timestamptz values back in the *session* time zone, so
    value.isoformat() can read "+08:00" on verify while the hash was created
    from "+00:00". Normalising to UTC on both sides keeps the hash stable.
    """
    if isinstance(value, str):
        return value
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def append_chain_record(cur, task_id, event_type, actor_id, event_data):
    """Append a single tamper-evident record to a task's custody chain.

    current_hash = SHA-256(previous_hash + canonical_event_json). Must be called
    inside the same transaction as the state change it records.
    """
    # Serialise writers per task: two simultaneous events must not both read the
    # same "last" record and fork the chain. The lock is released at commit.
    cur.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (str(task_id),))

    cur.execute(
        "SELECT sequence_number, current_hash FROM custody_chain "
        "WHERE task_id=%s ORDER BY sequence_number DESC LIMIT 1",
        (task_id,),
    )
    last = cur.fetchone()
    previous_hash = last["current_hash"] if last else GENESIS_HASH
    seq = (last["sequence_number"] + 1) if last else 1

    # Hash exactly what PostgreSQL will store: round-trip through canonical JSON
    # so tuples, key order, etc. cannot make the stored JSONB differ from the hash.
    event_data = json.loads(canonicalize(event_data))

    event_timestamp = datetime.now(timezone.utc)
    event_content = {
        "task_id": str(task_id),
        "event_type": event_type,
        "actor_id": str(actor_id) if actor_id else None,
        "event_data": event_data,
        "event_timestamp": _utc_iso(event_timestamp),
        "sequence_number": seq,
    }
    current_hash = compute_chain_hash(previous_hash, event_content)

    cur.execute(
        """INSERT INTO custody_chain
           (task_id, event_type, actor_id, event_data, event_timestamp,
            sequence_number, previous_hash, current_hash)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
        (task_id, event_type, actor_id, json.dumps(event_data), event_timestamp,
         seq, previous_hash, current_hash),
    )
    return current_hash


def verify_custody_chain(task_id):
    """Recompute and check every link of a task's custody chain.

    Returns a dict with status ("VALID" / "INVALID"), valid, record_count,
    last_verified and, when invalid, the FIRST broken record and why.
    """
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT id, task_id, event_type, actor_id, event_data,
                      event_timestamp, sequence_number, previous_hash, current_hash
               FROM custody_chain
               WHERE task_id=%s
               ORDER BY sequence_number ASC""",
            (task_id,),
        )
        records = cur.fetchall()

    now_iso = datetime.now(timezone.utc).isoformat()
    base = {"task_id": str(task_id), "record_count": len(records), "last_verified": now_iso}

    if not records:
        return {**base, "status": "VALID", "valid": True,
                "message": "No chain records found for this task."}

    expected_previous_hash = GENESIS_HASH
    for i, rec in enumerate(records):
        idx = i + 1
        broken = {**base, "status": "INVALID", "valid": False, "broken_record": idx,
                  "broken_sequence": rec["sequence_number"], "broken_record_id": str(rec["id"])}

        # 1. The link to the previous record.
        if rec["previous_hash"] != expected_previous_hash:
            return {**broken,
                    "reason": ("previous_hash link broken: this record does not reference the hash of "
                               "the preceding record (possible deletion, reordering or tampering)."),
                    "expected_previous_hash": expected_previous_hash,
                    "stored_previous_hash": rec["previous_hash"]}

        # 2. The record's own content.
        event_data = rec["event_data"]
        if isinstance(event_data, str):
            event_data = json.loads(event_data)
        event_content = {
            "task_id": str(rec["task_id"]),
            "event_type": rec["event_type"],
            "actor_id": str(rec["actor_id"]) if rec["actor_id"] else None,
            "event_data": event_data,
            "event_timestamp": _utc_iso(rec["event_timestamp"]),
            "sequence_number": rec["sequence_number"],
        }
        recomputed = compute_chain_hash(rec["previous_hash"], event_content)
        if recomputed != rec["current_hash"]:
            return {**broken,
                    "reason": ("current_hash mismatch: the stored hash does not match the recomputed "
                               "hash (possible modification of this record's content)."),
                    "expected_hash": recomputed, "stored_hash": rec["current_hash"]}

        expected_previous_hash = rec["current_hash"]

    return {**base, "status": "VALID", "valid": True, "message": "Chain is valid. All hashes verified."}
