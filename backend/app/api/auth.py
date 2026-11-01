"""
Account endpoints: sign up, sign in, sign out, and "who am I".

    POST /api/auth/signup    create an account and sign in (the email in ADMIN_EMAIL becomes the admin)
    POST /api/auth/login     sign in
    POST /api/auth/logout    sign out (this browser)
    POST /api/auth/forgot    email a password reset link (if the email has an account; the answer is the same either way)
    POST /api/auth/reset     choose a new password with that link's token; signs the account out everywhere
    GET  /api/auth/me        the signed-in account and its quota, or 401

How signing in works
    The answer sets a cookie holding a random session token. The cookie is HttpOnly (page scripts cannot read it, so a
    script injected into the page cannot steal it), SameSite=Lax (other sites cannot send it with their forms), and
    Secure on the deployed HTTPS site (COOKIE_SECURE). The database keeps only the token's fingerprint.

Guessing protection
    After 5 failed sign-ins for one email (or 20 from one address) within 15 minutes, further tries are refused for a
    while. Wrong email and wrong password get the same answer, in the same time, so the form does not reveal who has
    an account. At most 5 new accounts per address per hour. A password may not be the email or a very common one.
    Reset links: at most 3 a hour per email and 10 per address; a link works once, for 30 minutes.
    These counters live in memory: they reset when the server restarts and assume a single server (as deployed).
"""

import logging
import time
from collections import defaultdict, deque

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, Response
from app.api.deps import DbDep, SettingsDep
import sqlite3

from app.auth.access import LOCAL_USER, UserDep, cookie_name
from app.auth.passwords import hash_password, verify_password
from app.auth.quota import tokens_left, tokens_used
from app.db import users_repo
from app.mail.base import Mailer, MailError
from app.models.common import ArchwayModel
from app.models.user import ForgotPassword, ResetPassword, SignIn, SignUp, User

router = APIRouter(prefix="/auth", tags=["auth"])

WINDOW_SECONDS = 15 * 60
MAX_PER_EMAIL = 5
MAX_PER_ADDRESS = 20
SIGNUPS_PER_ADDRESS = 5  # new accounts from one address per hour
SIGNUP_WINDOW = 60 * 60
_signups: dict[str, deque[float]] = defaultdict(deque)
RESET_MINUTES = 30
RESET_WINDOW = 60 * 60
RESETS_PER_EMAIL = 3
RESETS_PER_ADDRESS = 10
_resets: dict[str, deque[float]] = defaultdict(deque)
logger = logging.getLogger("archway.api")
# A few of the passwords tried first by anyone guessing. Long enough to pass the length rule, so they are named here.
COMMON_PASSWORDS = {
    "password123", "password1234", "1234567890", "12345678910", "qwertyuiop", "qwerty12345", "letmein123", "iloveyou123",
    "abcdefghij", "1q2w3e4r5t", "passw0rd123", "welcome123", "admin12345", "archway123", "changeme123", "0000000000",
}
_failures: dict[str, deque[float]] = defaultdict(deque)
# A real hash of a random password: checked when the email is unknown, so an unknown email takes as long as a
# known one (the timing does not reveal which emails have accounts).
_DUMMY_HASH = hash_password("not-a-real-password-for-timing-only")


class Me(ArchwayModel):
    user: User
    tokens_used: int  # model tokens this month
    tokens_left: int | None  # None = no limit
    auth_enabled: bool = True


def _too_many(key: str, limit: int) -> bool:
    now = time.monotonic()
    tries = _failures[key]
    while tries and now - tries[0] > WINDOW_SECONDS:
        tries.popleft()
    return len(tries) >= limit


def _failed(*keys: str) -> None:
    for key in keys:
        _failures[key].append(time.monotonic())


def _weak(password: str, email: str) -> str | None:
    """Why a password is too easy to guess, or None."""
    lowered = password.lower()
    if lowered == email or lowered == email.split("@")[0]:
        return "Choose a password that is not your email address."
    if lowered in COMMON_PASSWORDS or len(set(password)) <= 2:
        return "That password is too easy to guess. Choose a longer or less common one."
    return None


def _address(request: Request) -> str:
    return f"ip:{request.client.host if request.client else '?'}"


def _set_cookie(response: Response, token: str, settings) -> None:
    response.set_cookie(
        cookie_name(settings), token, max_age=settings.session_days * 86400, httponly=True, samesite="lax",
        secure=settings.cookie_secure, path="/",
    )


async def _me(db, user: User, enabled: bool) -> Me:
    if user.id == LOCAL_USER.id:
        return Me(user=user, tokens_used=0, tokens_left=None, auth_enabled=enabled)
    return Me(user=user, tokens_used=await tokens_used(db, user.id), tokens_left=await tokens_left(db, user), auth_enabled=enabled)


@router.post("/signup")
async def sign_up(body: SignUp, request: Request, response: Response, db: DbDep, settings: SettingsDep) -> Me:
    if not settings.auth_enabled:
        raise HTTPException(status_code=400, detail="Accounts are switched off on this server.")
    address = _address(request)
    recent = _signups[address]
    while recent and time.monotonic() - recent[0] > SIGNUP_WINDOW:
        recent.popleft()
    if len(recent) >= SIGNUPS_PER_ADDRESS:
        raise HTTPException(status_code=429, detail="Too many new accounts from here. Try again later.")
    problem = _weak(body.password, body.email)
    if problem:
        raise HTTPException(status_code=422, detail=problem)
    if await users_repo.user_by_email(db, body.email):
        raise HTTPException(status_code=409, detail="An account with this email already exists. Sign in instead.")
    is_admin = settings.admin_email is not None and body.email == settings.admin_email.strip().lower()
    try:
        user = await users_repo.create_user(
            db, email=body.email, password_hash=hash_password(body.password), name=(body.name or "").strip() or None,
            role="admin" if is_admin else "user",
            quota=None if is_admin else (settings.default_monthly_quota or None),
        )
    except sqlite3.IntegrityError:  # two sign-ups with the same email at the same moment: the database refuses one
        raise HTTPException(status_code=409, detail="An account with this email already exists. Sign in instead.") from None
    recent.append(time.monotonic())
    if is_admin:
        await users_repo.claim_unowned_projects(db, user.id)  # projects from before accounts existed are the admin's
    _set_cookie(response, await users_repo.create_session(db, user.id, settings.session_days), settings)
    return await _me(db, user, True)


@router.post("/login")
async def sign_in(body: SignIn, request: Request, response: Response, db: DbDep, settings: SettingsDep) -> Me:
    if not settings.auth_enabled:
        raise HTTPException(status_code=400, detail="Accounts are switched off on this server.")
    address = _address(request)
    email = f"email:{body.email}"
    if _too_many(email, MAX_PER_EMAIL) or _too_many(address, MAX_PER_ADDRESS):
        raise HTTPException(status_code=429, detail="Too many attempts. Wait a few minutes and try again.")
    found = await users_repo.user_by_email(db, body.email)
    if found is None:
        verify_password(body.password, _DUMMY_HASH)
        _failed(email, address)
        raise HTTPException(status_code=401, detail="That email and password do not match.")
    user, stored = found
    if not verify_password(body.password, stored):
        _failed(email, address)
        raise HTTPException(status_code=401, detail="That email and password do not match.")
    if user.status == "blocked":
        raise HTTPException(status_code=403, detail="This account is blocked. Contact the admin.")
    _failures.pop(email, None)
    await users_repo.end_expired_sessions(db)
    # A NEW random session every time (never one the browser already had): a planted session cannot be taken over.
    _set_cookie(response, await users_repo.create_session(db, user.id, settings.session_days), settings)
    await users_repo.touch(db, user.id)
    return await _me(db, user, True)


@router.post("/logout", status_code=204)
async def sign_out(request: Request, response: Response, db: DbDep, settings: SettingsDep) -> None:
    name = cookie_name(settings)
    token = request.cookies.get(name)
    if token:
        await users_repo.end_session(db, token)  # the session ends on the server, not only in this browser
    response.delete_cookie(name, path="/", secure=settings.cookie_secure, httponly=True, samesite="lax")


@router.post("/forgot", status_code=204)
async def forgot_password(body: ForgotPassword, request: Request, background: BackgroundTasks, db: DbDep,
                          settings: SettingsDep) -> None:
    """Emails a reset link, if there is an account. The answer is the same either way (see the notes at the top)."""
    mailer = request.app.state.mailer
    if not settings.auth_enabled or mailer is None:
        raise HTTPException(status_code=503, detail="Password reset by email is not set up on this server. Ask the admin.")
    if _too_many_resets(_address(request), RESETS_PER_ADDRESS):
        raise HTTPException(status_code=429, detail="Too many reset requests from here. Try again later.")
    found = await users_repo.user_by_email(db, body.email)
    # An unknown or blocked account, or too many links for one email this hour: nothing is sent, and the answer is
    # the same, so this form cannot be used to find out who has an account.
    if found is None or found[0].status != "active" or _too_many_resets(f"email:{body.email}", RESETS_PER_EMAIL):
        return
    token = await users_repo.create_reset(db, found[0].id, RESET_MINUTES)
    link = f"{_site_url(settings)}/#/login/reset/{token}"
    # Sent AFTER the answer (a background task): sending takes a moment, and an answer that is slower only for real
    # accounts would give them away.
    background.add_task(_send_reset_email, mailer, body.email, link)


@router.post("/reset", status_code=204)
async def reset_password(body: ResetPassword, request: Request, db: DbDep, settings: SettingsDep) -> None:
    """Sets a new password with an emailed link, and signs the account out everywhere."""
    if not settings.auth_enabled:
        raise HTTPException(status_code=400, detail="Accounts are switched off on this server.")
    address = _address(request)
    if _too_many(address, MAX_PER_ADDRESS):
        raise HTTPException(status_code=429, detail="Too many attempts. Wait a few minutes and try again.")
    user_id = await users_repo.reset_owner(db, body.token)
    if user_id is None:
        _failed(address)
        raise HTTPException(status_code=400, detail="This reset link has expired or was already used. Ask for a new one.")
    user = await users_repo.get_user(db, user_id)
    problem = _weak(body.password, user.email)
    if problem:
        raise HTTPException(status_code=422, detail=problem)  # the link still works: they can try another password
    if await users_repo.use_reset(db, body.token) != user_id:  # used up a moment ago by another request
        raise HTTPException(status_code=400, detail="This reset link has expired or was already used. Ask for a new one.")
    await users_repo.set_password(db, user_id, hash_password(body.password))
    # Whoever knew the old password is signed out everywhere.
    await users_repo.end_all_sessions(db, user_id)
    _failures.pop(f"email:{user.email}", None)
    logger.info("password reset", extra={"fields": {"user_id": user_id}})


def _too_many_resets(key: str, limit: int) -> bool:
    now = time.monotonic()
    recent = _resets[key]
    while recent and now - recent[0] > RESET_WINDOW:
        recent.popleft()
    if len(recent) >= limit:
        return True
    recent.append(now)
    return False


def _site_url(settings) -> str:
    if settings.public_site_url:
        return settings.public_site_url.rstrip("/")
    return settings.origin_list[0].rstrip("/") if settings.origin_list else "http://localhost:5173"


async def _send_reset_email(mailer: Mailer, to: str, link: str) -> None:
    text = (
        "Someone (hopefully you) asked to reset the password of your Archway account.\n\n"
        f"Choose a new password here (the link works once, for {RESET_MINUTES} minutes):\n{link}\n\n"
        "If it was not you, ignore this email: your password stays as it is."
    )
    html = (
        "<p>Someone (hopefully you) asked to reset the password of your Archway account.</p>"
        f'<p><a href="{link}">Choose a new password</a> (the link works once, for {RESET_MINUTES} minutes).</p>'
        "<p>If it was not you, ignore this email: your password stays as it is.</p>"
    )
    try:
        await mailer.send(to=to, subject="Reset your Archway password", text=text, html=html)
    except MailError as error:
        logger.warning("reset email not sent", extra={"fields": {"error": str(error)}})


@router.get("/me")
async def who_am_i(user: UserDep, db: DbDep, settings: SettingsDep) -> Me:
    return await _me(db, user, settings.auth_enabled)
