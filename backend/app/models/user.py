"""
Accounts: what an account is, what sign-up and sign-in send, and what the admin sees and changes.

    User         an account as the app shows it (never with its password hash)
    SignUp       email, password and an optional name
    SignIn       email and password
    ForgotPassword / ResetPassword   asking for a reset link, and choosing a new password with it
    UserChange   what the admin may change: the monthly token quota, blocked or not, admin or not
    UserUsage    one account's live usage this month, for the admin dashboard

Passwords are only ever hashed (app/auth/passwords.py); no model here carries one back out.
"""

from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator

from app.models.common import ArchwayModel

Role = Literal["user", "admin"]
Status = Literal["active", "blocked"]
MIN_PASSWORD = 10


class User(ArchwayModel):
    id: str
    email: str
    name: str | None = None
    role: Role
    status: Status
    monthly_token_quota: int | None  # None = no limit
    created_at: datetime
    last_seen_at: datetime | None = None


def _email(value: str) -> str:
    value = value.strip().lower()
    local, _, domain = value.partition("@")
    if not local or "." not in domain or " " in value or len(value) > 254:
        raise ValueError("enter a valid email address")
    return value


class SignUp(ArchwayModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=MIN_PASSWORD, max_length=200)
    name: str | None = Field(default=None, max_length=80)

    _check_email = field_validator("email")(lambda cls, value: _email(value))


class SignIn(ArchwayModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=200)

    _check_email = field_validator("email")(lambda cls, value: value.strip().lower())


class ForgotPassword(ArchwayModel):
    email: str = Field(min_length=3, max_length=254)

    _check_email = field_validator("email")(lambda cls, value: value.strip().lower())


class ResetPassword(ArchwayModel):
    token: str = Field(min_length=20, max_length=200)  # from the emailed link
    password: str = Field(min_length=MIN_PASSWORD, max_length=200)


class UserChange(ArchwayModel):
    """Only the fields sent are changed. A quota of 0 means no limit."""

    monthly_token_quota: int | None = Field(default=None, ge=0, le=10_000_000_000)
    status: Status | None = None
    role: Role | None = None


class UserUsage(ArchwayModel):
    user: User
    tokens: int  # model tokens this calendar month
    llm_calls: int
    decision_calls: int
    github_calls: int
    runs: int  # runs started this month
    projects: int
    working: bool  # a run of theirs is working right now
    quota_left: int | None  # None = no limit
