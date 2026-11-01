"""
Saving and loading accounts and sign-in sessions.

What this file does
    accounts   create_user, user_by_email (with the password hash, for signing in only), get_user, list_users,
               change_user, touch (last seen), count_admins, claim_unowned_projects
    sessions   create_session (returns the random token for the cookie), user_for_session, end_session,
               end_all_sessions
    resets     create_reset (returns the random token for the emailed link), reset_owner, use_reset, set_password

LEARNING NOTE: what is stored for a session
    The browser keeps a long random token in a cookie. The database keeps only its SHA-256 fingerprint. To check a
    request, the token from the cookie is fingerprinted again and looked up. Someone who copies the database learns
    nothing they could put in a cookie. (A fast hash is fine HERE, unlike for passwords: the token is 32 random bytes,
    so there is nothing to guess.)
"""

import hashlib
import secrets
from datetime import timedelta

import aiosqlite

from app.db.errors import NotFound
from app.models.common import new_id, utc_now
from app.models.user import Role, User


def _to_user(row: aiosqlite.Row) -> User:
    values = dict(row)
    values.pop("password_hash", None)
    return User(**values)


def fingerprint(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def create_user(connection: aiosqlite.Connection, *, email: str, password_hash: str, name: str | None,
                      role: Role, quota: int | None) -> User:
    now = utc_now().isoformat()
    user_id = new_id()
    await connection.execute(
        "INSERT INTO users (id, email, name, password_hash, role, status, monthly_token_quota, created_at) VALUES (?, ?, ?, ?, ?, 'active', ?, ?)",
        (user_id, email, name, password_hash, role, quota, now),
    )
    await connection.commit()
    return await get_user(connection, user_id)


async def user_by_email(connection: aiosqlite.Connection, email: str) -> tuple[User, str] | None:
    """The account and its password hash, for signing in. None if there is no such account."""
    cursor = await connection.execute("SELECT * FROM users WHERE email = ?", (email,))
    row = await cursor.fetchone()
    return (_to_user(row), row["password_hash"]) if row else None


async def get_user(connection: aiosqlite.Connection, user_id: str) -> User:
    cursor = await connection.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    row = await cursor.fetchone()
    if row is None:
        raise NotFound("user", user_id)
    return _to_user(row)


async def list_users(connection: aiosqlite.Connection) -> list[User]:
    cursor = await connection.execute("SELECT * FROM users ORDER BY created_at")
    return [_to_user(row) for row in await cursor.fetchall()]


async def change_user(connection: aiosqlite.Connection, user_id: str, fields: dict) -> User:
    await get_user(connection, user_id)  # 404 for an unknown account
    allowed = {key: value for key, value in fields.items() if key in {"monthly_token_quota", "status", "role", "name"}}
    if allowed:
        assignments = ", ".join(f"{key} = ?" for key in allowed)  # the names come from the fixed list above
        await connection.execute(f"UPDATE users SET {assignments} WHERE id = ?", (*allowed.values(), user_id))
        await connection.commit()
    return await get_user(connection, user_id)


async def touch(connection: aiosqlite.Connection, user_id: str) -> None:
    await connection.execute("UPDATE users SET last_seen_at = ? WHERE id = ?", (utc_now().isoformat(), user_id))
    await connection.commit()


async def count_admins(connection: aiosqlite.Connection) -> int:
    cursor = await connection.execute("SELECT COUNT(*) AS n FROM users WHERE role = 'admin' AND status = 'active'")
    return int((await cursor.fetchone())["n"])


async def claim_unowned_projects(connection: aiosqlite.Connection, user_id: str) -> int:
    """Projects made before accounts existed have no owner; give them to this (admin) account."""
    cursor = await connection.execute("UPDATE projects SET owner_id = ? WHERE owner_id IS NULL", (user_id,))
    await connection.commit()
    return cursor.rowcount


# --- Sessions ------------------------------------------------------------------------------------------------------


async def create_session(connection: aiosqlite.Connection, user_id: str, days: int) -> str:
    token = secrets.token_urlsafe(32)
    now = utc_now()
    await connection.execute(
        "INSERT INTO sessions (token_hash, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
        (fingerprint(token), user_id, now.isoformat(), (now + timedelta(days=days)).isoformat()),
    )
    await connection.commit()
    return token


async def user_for_session(connection: aiosqlite.Connection, token: str) -> User | None:
    """The account a session token belongs to, if the session is current and the account is not blocked."""
    cursor = await connection.execute(
        "SELECT users.* FROM sessions JOIN users ON users.id = sessions.user_id "
        "WHERE sessions.token_hash = ? AND sessions.expires_at > ? AND users.status = 'active'",
        (fingerprint(token), utc_now().isoformat()),
    )
    row = await cursor.fetchone()
    return _to_user(row) if row else None


async def end_session(connection: aiosqlite.Connection, token: str) -> None:
    await connection.execute("DELETE FROM sessions WHERE token_hash = ?", (fingerprint(token),))
    await connection.commit()


async def end_expired_sessions(connection: aiosqlite.Connection) -> None:
    await connection.execute("DELETE FROM sessions WHERE expires_at <= ?", (utc_now().isoformat(),))
    await connection.commit()


async def end_all_sessions(connection: aiosqlite.Connection, user_id: str) -> None:
    await connection.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
    await connection.commit()


# --- Password resets ---------------------------------------------------------------------------------------------------


async def create_reset(connection: aiosqlite.Connection, user_id: str, minutes: int) -> str:
    """A new reset link token for the account (only its fingerprint is stored). Older unused links stop working."""
    token = secrets.token_urlsafe(32)
    now = utc_now()
    await connection.execute("DELETE FROM password_resets WHERE user_id = ? OR expires_at <= ?", (user_id, now.isoformat()))
    await connection.execute(
        "INSERT INTO password_resets (token_hash, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
        (fingerprint(token), user_id, now.isoformat(), (now + timedelta(minutes=minutes)).isoformat()),
    )
    await connection.commit()
    return token


async def reset_owner(connection: aiosqlite.Connection, token: str) -> str | None:
    """The account a reset token belongs to, if it is unused and current (without using it)."""
    cursor = await connection.execute(
        "SELECT user_id FROM password_resets WHERE token_hash = ? AND used_at IS NULL AND expires_at > ?",
        (fingerprint(token), utc_now().isoformat()),
    )
    row = await cursor.fetchone()
    return row["user_id"] if row else None


async def use_reset(connection: aiosqlite.Connection, token: str) -> str | None:
    """The account a reset token belongs to, marking it used, or None (unknown, used or expired).

    LEARNING NOTE: one statement, so a link cannot be used twice
        Checking "is it unused?" and then marking it used in two steps leaves a gap in which two requests could both
        pass the check. A single UPDATE ... WHERE used_at IS NULL ... RETURNING does both at once: only one request
        can change the row, and only that one gets the account back.
    """
    now = utc_now().isoformat()
    cursor = await connection.execute(
        "UPDATE password_resets SET used_at = ? WHERE token_hash = ? AND used_at IS NULL AND expires_at > ? RETURNING user_id",
        (now, fingerprint(token), now),
    )
    row = await cursor.fetchone()
    await connection.commit()
    return row["user_id"] if row else None


async def set_password(connection: aiosqlite.Connection, user_id: str, password_hash: str) -> None:
    await connection.execute("UPDATE users SET password_hash = ? WHERE id = ?", (password_hash, user_id))
    await connection.commit()
