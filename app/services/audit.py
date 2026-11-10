"""Audit-log writer."""



def audit(cur, actor_id, action, entity_type=None, entity_id=None, details=None):
    cur.execute(
        "INSERT INTO audit_logs(actor_id, action, entity_type, entity_id, details) VALUES (%s,%s,%s,%s,%s)",
        (actor_id, action, entity_type, entity_id, details),
    )
