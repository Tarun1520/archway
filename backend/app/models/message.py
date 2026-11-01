"""
Message: one entry in a project's chat.

How it plugs in
    app/db/messages_repo.py saves and loads `Message`.
    app/api/messages.py receives `MessageCreate`.
    In Phase 2 the `intake` node reads the user's messages from here.
"""

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.models.common import ArchwayModel

Role = Literal["user", "assistant", "system"]


class Message(ArchwayModel):
    id: str
    project_id: str
    role: Role
    content: str
    created_at: datetime


class MessageCreate(ArchwayModel):
    role: Role = "user"
    content: str = Field(min_length=1, max_length=8000)
