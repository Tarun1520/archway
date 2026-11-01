"""
Project: one idea the user is working on.

What this file does
    Defines the stored project, plus the two request bodies the API accepts.

LEARNING NOTE: why three classes for one thing?
    - `Project`        what is stored and returned (has an id and dates).
    - `ProjectCreate`  what the client SENDS to make one (no id: we create it).
    - `ProjectUpdate`  what the client sends to change one (every field optional).
    Keeping them apart means a client can never set its own id or dates.

How it plugs in
    app/db/projects_repo.py saves and loads `Project`.
    app/api/projects.py receives `ProjectCreate` / `ProjectUpdate`.
"""

from datetime import datetime

from pydantic import Field

from app.models.common import ArchwayModel

MAX_IDEA_LENGTH = 2000  # the same limit the welcome page enforces


class Project(ArchwayModel):
    id: str
    name: str
    idea: str | None = None  # the original text the user typed, if any
    created_at: datetime
    updated_at: datetime


class ProjectCreate(ArchwayModel):
    name: str = Field(min_length=1, max_length=120)
    idea: str | None = Field(default=None, max_length=MAX_IDEA_LENGTH)


class ProjectUpdate(ArchwayModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
