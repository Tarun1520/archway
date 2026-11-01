"""
Voice passes: a short-lived ticket that lets the voice WebSocket sign in without the cookie.

Why this exists
    On the deployed site the page lives on Vercel, and Vercel forwards /api/* to the server, so the sign-in cookie
    belongs to the Vercel address. Vercel's forwarding does not carry WebSockets, though, so the microphone stream
    has to go STRAIGHT to the server's own address, and the browser does not send the Vercel cookie there.

    So the page first asks, through Vercel (cookie and all), for a pass:  POST /api/voice/pass
    and then opens  wss://<server>/api/voice/listen?pass=<pass>.  The server swaps the pass for the account.

What keeps a pass safe
    - It is random (32 bytes), so it cannot be guessed.
    - It works ONCE: redeeming it removes it, so a pass seen in a log is already used up.
    - It expires after PASS_SECONDS, so an unused one does not linger.
    - The WebSocket is still Origin-checked (app/security/guard.py), so another website cannot use one.

LEARNING NOTE: kept in memory, on purpose
    The passes live in a plain dict on this process, not in the database. They last seconds, and losing them on a
    restart costs nothing (the page simply asks again). This works because the server runs ONE backend process;
    with several, each would need to see the same passes (the database, or Redis).
"""

import secrets
import time

PASS_SECONDS = 60

# pass -> (user id, the moment it expires)
_passes: dict[str, tuple[str, float]] = {}


def issue(user_id: str) -> str:
    _forget_expired()
    token = secrets.token_urlsafe(32)
    _passes[token] = (user_id, time.monotonic() + PASS_SECONDS)
    return token


def redeem(token: str) -> str | None:
    """The account the pass was given to, or None (unknown, used or expired). A pass works only once."""
    entry = _passes.pop(token, None)
    if entry is None:
        return None
    user_id, expires = entry
    return user_id if time.monotonic() < expires else None


def _forget_expired() -> None:
    now = time.monotonic()
    for token in [token for token, (_, expires) in _passes.items() if expires <= now]:
        del _passes[token]
