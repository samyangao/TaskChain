"""IT 107 activity-log monitor.

Run from the command line:
    python scripts/monitor.py

It scans the last 24 hours, detects the four patterns from the handout,
writes new findings to security_flags (one per pattern/target/day) and prints
a console report. The file lives outside frontend/, so a browser request to
/scripts/monitor.py is a 404.
"""

import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.config import IP_BLOCK_THRESHOLD  # noqa: E402
from app.db import db  # noqa: E402
from app.services.activity import PHT  # noqa: E402

FAILURE_EVENTS = ("LOGIN_FAILED", "SECURITY_ANSWER_FAILED", "OTP_FAILED", "CAPTCHA_FAILED")


def _rows(cur, sql, params=()):
    cur.execute(sql, params)
    return cur.fetchall()


def detect(cur):
    findings = []

    # 1. One IP at or above the seeded threshold, across any usernames.
    rows = _rows(
        cur,
        """SELECT host(ip_address) AS ip, count(*) AS failures,
                  count(DISTINCT username_typed) AS usernames
             FROM activity_log
            WHERE event_type = ANY(%s)
              AND ip_address IS NOT NULL
              AND created_at >= now() - interval '24 hours'
            GROUP BY ip_address
           HAVING count(*) >= %s
            ORDER BY failures DESC""",
        (list(FAILURE_EVENTS), IP_BLOCK_THRESHOLD),
    )
    for row in rows:
        findings.append({
            "pattern": "IP over threshold",
            "target": row["ip"],
            "severity": "HIGH",
            "details": f"{row['failures']} failures, {row['usernames']} usernames",
        })

    # 2. One account attacked from three or more distinct IPs.
    rows = _rows(
        cur,
        """SELECT username_typed AS target, count(DISTINCT ip_address) AS ips
             FROM activity_log
            WHERE event_type = ANY(%s)
              AND username_typed IS NOT NULL AND username_typed <> ''
              AND ip_address IS NOT NULL
              AND created_at >= now() - interval '24 hours'
            GROUP BY username_typed
           HAVING count(DISTINCT ip_address) >= 3
            ORDER BY ips DESC""",
        (list(FAILURE_EVENTS),),
    )
    for row in rows:
        findings.append({
            "pattern": "Account targeted",
            "target": row["target"],
            "severity": "MED",
            "details": f"failures from {row['ips']} IPs",
        })

    # 3. Five or more wrong OTPs for one account inside any 10-minute window.
    rows = _rows(
        cur,
        """SELECT username_typed, created_at
             FROM activity_log
            WHERE event_type='OTP_FAILED'
              AND username_typed IS NOT NULL AND username_typed <> ''
              AND created_at >= now() - interval '24 hours'
            ORDER BY username_typed, created_at""",
    )
    by_account = defaultdict(list)
    for row in rows:
        by_account[row["username_typed"]].append(row["created_at"])
    for account, times in by_account.items():
        left = 0
        for right, moment in enumerate(times):
            while moment - times[left] > timedelta(minutes=10):
                left += 1
            if right - left + 1 >= 5:
                findings.append({
                    "pattern": "OTP guessing",
                    "target": account,
                    "severity": "MED",
                    "details": f"{right - left + 1} wrong OTPs in 10 min",
                })
                break

    # 4. Successful log-in between 12:00 AM and 5:00 AM Philippine time.
    rows = _rows(
        cur,
        """SELECT username_typed, created_at
             FROM activity_log
            WHERE event_type='LOGIN_SUCCESS'
              AND created_at >= now() - interval '24 hours'
              AND EXTRACT(hour FROM created_at AT TIME ZONE 'Asia/Manila') < 5
            ORDER BY created_at DESC""",
    )
    seen = set()
    for row in rows:
        target = row["username_typed"] or "unknown"
        if target in seen:
            continue
        seen.add(target)
        findings.append({
            "pattern": "Off-hours log-in",
            "target": target,
            "severity": "MED",
            "details": f"successful log-in at {row['created_at'].astimezone(PHT):%I:%M %p} PHT",
        })

    return findings


def write_flags(cur, findings):
    today = datetime.now(PHT).date()
    new_flags = 0
    for finding in findings:
        cur.execute(
            """INSERT INTO security_flags(pattern, target, severity, details, flag_date)
               VALUES (%s,%s,%s,%s,%s)
               ON CONFLICT (pattern, target, flag_date) DO NOTHING""",
            (finding["pattern"], finding["target"], finding["severity"],
             finding["details"], today),
        )
        new_flags += cur.rowcount
    return new_flags


def main():
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT count(*) AS n FROM activity_log WHERE created_at >= now() - interval '24 hours'"
        )
        scanned = int(cur.fetchone()["n"])

        findings = detect(cur)
        new_flags = write_flags(cur, findings)

        cur.execute(
            "SELECT count(*) AS n FROM security_flags WHERE flag_date=%s",
            (datetime.now(PHT).date(),),
        )
        total_today = int(cur.fetchone()["n"])

    stamp = datetime.now(PHT).strftime("%Y-%m-%d %H:%M PHT")
    print(f"IT 107 Monitoring Report  -  {stamp}")
    print(f"Scanned: {scanned:,} events (last 24 hours)")
    if not findings:
        print("No suspicious patterns found.")
    for finding in findings:
        tag = f"[{finding['severity']:<4}]"
        print(f"{tag} {finding['pattern']:<20} {finding['target']:<24} {finding['details']}")
    print()
    print(f"New flags written: {new_flags}      Already flagged today: {total_today - new_flags}")


if __name__ == "__main__":
    main()
