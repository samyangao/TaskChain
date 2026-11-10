"""Small shared helpers: JSON errors, UUID parsing, client IP, IP throttling."""

import time
from collections import defaultdict, deque
from flask import jsonify, request
from uuid import UUID
from app.config import IP_MAX_ATTEMPTS, IP_WINDOW_SECONDS


def json_error(message, status=400):
    return jsonify(error=message), status


def parse_uuid(value):
    """Return a UUID, or None when the value is not a well-formed identifier."""
    try:
        return UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        return None


def client_ip():
    return request.remote_addr or "unknown"


_ip_hits = defaultdict(deque)


def ip_throttled(key="default", limit=IP_MAX_ATTEMPTS, window=IP_WINDOW_SECONDS):
    """Simple in-process sliding-window throttle that also prunes stale entries."""
    now = time.monotonic()
    bucket = _ip_hits[(key, client_ip())]
    while bucket and now - bucket[0] > window:
        bucket.popleft()
    if len(bucket) >= limit:
        return int(window - (now - bucket[0])) + 1
    bucket.append(now)
    if len(_ip_hits) > 4096:  # bound memory if the key space grows
        for stale in [k for k, v in _ip_hits.items() if not v or now - v[-1] > window]:
            del _ip_hits[stale]
    return 0


def _short(text, limit=120):
    text = " ".join(str(text or "").split())
    return text if len(text) <= limit else text[: limit - 1] + "…"
