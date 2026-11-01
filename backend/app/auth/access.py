"""
Who is asking, and may they see this?

What this file does (FastAPI dependencies)
    current_user      the signed-in account (from the session cookie), or HTTP 401. With auth switched off, the
                      built-in local admin.
    require_admin     the same, but only an admin (HTTP 403 otherwise)
    owns_path         used on whole routers: if the address names a project or a run, it must belong to the person
                      asking (an admin too: admins see usage counts, never other people's projects). Otherwise HTTP 404, the same answer as for something that does
                      not exist, so nobody can probe which ids exist.

LEARNING NOTE: one check for many routes
    Every project and run endpoint has `{project_id}` or `{run_id}` in its address. Instead of repeating an ownership
    check in each of them, `owns_path` is attached to the routers (app/main.py) and reads those two values from the
    address before the route runs. A new endpoint under those routers is protected without anyone remembering to.
    They take an HTTPConnection (the parent of a request and a WebSocket), so the voice WebSocket is covered as well.
"""

from datetime import datetime, timezone
from typing import Annotated

from fastapi import Depends, HTTPException
from starlette.requests import HTTPConnection

from app.api.deps import DbDep
from app.auth import voice_pass
from app.db import users_repo
from app.db.errors import NotFound
from app.models.user import User

COOKIE = "archway_session"
# On the HTTPS site the cookie is named with the "__Host-" prefix: browsers then accept it only if it is Secure,
# for this exact host, for the whole site, so a neighbouring subdomain can never plant or overwrite it.
SECURE_COOKIE = "__Host-archway_session"


def cookie_name(settings) -> str:
    return SECURE_COOKIE if settings.cookie_secure else COOKIE
# Used when AUTH_ENABLED=false: one person, on their own machine, who may do everything.
LOCAL_USER = User(id="local", email="local@archway", name="Local", role="admin", status="active",
                  monthly_token_quota=None, created_at=datetime(2026, 1, 1, tzinfo=timezone.utc))


async def current_user(request: HTTPConnection, db: DbDep) -> User:
    if not request.app.state.settings.auth_enabled:
        return LOCAL_USER
    token = request.cookies.get(cookie_name(request.app.state.settings))
    user = await users_repo.user_for_session(db, token) if token else None
    if user is None and request.scope["type"] == "websocket" and request.query_params.get("pass"):
        user = await _user_for_pass(db, request.query_params["pass"])
    if user is None:
        raise HTTPException(status_code=401, detail="Sign in to continue.")
    seen = user.last_seen_at
    if seen is None or (datetime.now(timezone.utc) - seen).total_seconds() > 60:
        await users_repo.touch(db, user.id)  # at most once a minute, so it costs nothing per request
    return user


async def _user_for_pass(db, token: str) -> User | None:
    """The voice WebSocket opened on the server's own address carries a one-time pass instead of the cookie
    (app/auth/voice_pass.py). Only WebSockets accept one, so a pass can never stand in for the cookie elsewhere."""
    user_id = voice_pass.redeem(token)
    if user_id is None:
        return None
    try:
        user = await users_repo.get_user(db, user_id)
    except NotFound:
        return None
    return user if user.status == "active" else None


UserDep = Annotated[User, Depends(current_user)]


async def require_admin(user: UserDep) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Only an admin can do that.")
    return user


AdminDep = Annotated[User, Depends(require_admin)]


def owner_filter(user: User) -> str | None:
    """Whose projects a list shows: the account's own (None = no filter: auth off)."""
    return None if user.id == LOCAL_USER.id else user.id


# LEARNING NOTE: an admin sees usage, not content
#   The admin dashboard shows how much each account has used, never what they are building. So being an admin
#   gives NO access to other people's projects or runs here: only the built-in local user (accounts switched off,
#   one person on their own machine) sees everything.


async def can_see_project(db, project_id: str, user: User) -> bool:
    if user.id == LOCAL_USER.id:
        return True
    cursor = await db.execute("SELECT owner_id FROM projects WHERE id = ?", (project_id,))
    row = await cursor.fetchone()
    return row is None or row["owner_id"] == user.id  # an unknown id falls through to the route's own 404


async def can_see_run(db, run_id: str, user: User) -> bool:
    if user.id == LOCAL_USER.id:
        return True
    cursor = await db.execute("SELECT projects.owner_id FROM runs JOIN projects ON projects.id = runs.project_id WHERE runs.id = ?", (run_id,))
    row = await cursor.fetchone()
    return row is None or row["owner_id"] == user.id


async def owns_path(request: HTTPConnection, user: UserDep, db: DbDep) -> None:
    params = request.path_params
    if "project_id" in params and not await can_see_project(db, params["project_id"], user):
        raise HTTPException(status_code=404, detail=f"project '{params['project_id']}' was not found")
    if "run_id" in params and not await can_see_run(db, params["run_id"], user):
        raise HTTPException(status_code=404, detail=f"run '{params['run_id']}' was not found")
