"""AES-256 encryption for sensitive registration data.

PostgreSQL's pgcrypto uses AES-256 with a random salt/IV for
pgp_sym_encrypt/pgp_sym_decrypt. The key is FIELD_ENCRYPTION_KEY, kept in
.env outside the served frontend/ root. Storing the key in the database
connection process (not in the SQL text) keeps it out of query logs.
"""

import hashlib
import os

from flask import current_app

from app.log import logger


def _key() -> str:
    raw = os.environ.get("FIELD_ENCRYPTION_KEY", "").strip()
    if raw and raw != "replace_with_32_random_bytes_base64":
        return raw
    logger.warning(
        "FIELD_ENCRYPTION_KEY is not set; deriving a development key from FLASK_SECRET_KEY"
    )
    return hashlib.sha256(("taskchain-field:" + current_app.secret_key).encode()).hexdigest()


def encrypt_field(cur, plaintext: str) -> bytes:
    """Return pgp_sym_encrypt(plaintext, key), which is AES-256 ciphertext."""
    cur.execute("SELECT pgp_sym_encrypt(%s, %s) AS encrypted", (str(plaintext), _key()))
    return cur.fetchone()["encrypted"]


def decrypt_field(cur, blob: bytes) -> str:
    """Decrypt a value for its owner. Raises on a wrong key or tampering."""
    cur.execute("SELECT pgp_sym_decrypt(%s, %s)::text AS plaintext", (blob, _key()))
    return cur.fetchone()["plaintext"]
