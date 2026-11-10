"""Small dependency-free TOTP (RFC 6238) helpers used by Phase 9.

Secrets are generated here, but stored encrypted by PostgreSQL pgcrypto.
The application never stores the plaintext secret in the database.
"""

import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote

DIGITS = 6
STEP_SECONDS = 30
WINDOW = 1  # accept the previous, current and next 30-second step


def generate_secret(byte_length=20):
    """Return a base32 secret (no padding), as expected by authenticator apps."""
    return base64.b32encode(secrets.token_bytes(byte_length)).decode("ascii").rstrip("=")


def _decode_secret(secret):
    secret = "".join(str(secret or "").split()).upper()
    if not secret:
        raise ValueError("empty TOTP secret")
    padding = "=" * ((8 - len(secret) % 8) % 8)
    return base64.b32decode(secret + padding, casefold=True)


def code_at(secret, timestamp=None, step=STEP_SECONDS, digits=DIGITS):
    """Return (code, counter) for a timestamp (seconds since the epoch)."""
    counter = int((time.time() if timestamp is None else timestamp) // step)
    digest = hmac.new(_decode_secret(secret), struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF
    return f"{value % (10 ** digits):0{digits}d}", counter


def verify_code(secret, code, timestamp=None, window=WINDOW):
    """Check a code against the current step and its neighbours.

    Returns (ok, counter). The counter is stored by the caller so a code can
    never be replayed, even inside the accepted time window.
    """
    code = "".join(str(code or "").split())
    if not code.isdigit() or len(code) != DIGITS:
        return False, 0
    try:
        base = int((time.time() if timestamp is None else timestamp) // STEP_SECONDS)
    except (TypeError, ValueError):
        return False, 0
    for offset in range(-window, window + 1):
        candidate, counter = code_at(secret, timestamp=(base + offset) * STEP_SECONDS)
        if hmac.compare_digest(candidate, code):
            return True, counter
    return False, 0


def provisioning_uri(secret, account, issuer="TaskChain"):
    """otpauth:// URI that authenticator apps understand (and can turn into a QR code)."""
    label = f"{issuer}:{account}"
    return (
        f"otpauth://totp/{quote(label)}?secret={secret}"
        f"&issuer={quote(issuer)}&algorithm=SHA1&digits={DIGITS}&period={STEP_SECONDS}"
    )
