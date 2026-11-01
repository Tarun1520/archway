"""
Storing passwords safely.

What this file does
    hash_password("...")            -> "scrypt$16384$8$1$<salt>$<hash>"
    verify_password("...", stored)  -> True or False

LEARNING NOTE: why a slow, salted hash
    A password is never stored, only a fingerprint of it. A fast fingerprint (like SHA-256) can be tried billions of
    times a second by someone who copies the database. scrypt is deliberately slow AND needs a lot of memory for each
    try, which makes guessing expensive. A random SALT per password means two people with the same password get
    different fingerprints, so one guess can never crack many accounts at once. scrypt is in Python's own library
    (hashlib), so no extra package is needed.

    The settings (N, r, p) are stored with each hash, so they can be raised later without breaking old accounts.
"""

import base64
import hashlib
import hmac
import secrets

N, R, P = 2**14, 8, 1  # cost: ~16 MB of memory and a few tens of milliseconds per check
KEY_LENGTH = 32


def _encode(data: bytes) -> str:
    return base64.b64encode(data).decode()


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=N, r=R, p=P, dklen=KEY_LENGTH)
    return f"scrypt${N}${R}${P}${_encode(salt)}${_encode(digest)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt, digest = stored.split("$")
        if scheme != "scrypt":
            return False
        expected = base64.b64decode(digest)
        actual = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt), n=int(n), r=int(r), p=int(p), dklen=len(expected))
    except (ValueError, TypeError):
        return False
    # LEARNING NOTE: compare_digest takes the same time whether the first byte or the last one differs, so the
    #   time an answer takes reveals nothing about how close a guess was.
    return hmac.compare_digest(actual, expected)
