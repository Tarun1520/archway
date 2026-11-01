"""
Message endpoints.

    POST /api/projects/{id}/messages   add a message to a project's chat
    GET  /api/projects/{id}/messages   list them, oldest first

In Phase 1 a message is only stored. In Phase 2, posting a user message will
also start or continue the workflow.
"""

from fastapi import APIRouter, status

from app.api.deps import DbDep
from app.db import messages_repo
from app.models.message import Message, MessageCreate

router = APIRouter(prefix="/projects/{project_id}/messages", tags=["messages"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def add_message(project_id: str, data: MessageCreate, db: DbDep) -> Message:
    return await messages_repo.add_message(db, project_id, data)


@router.get("")
async def list_messages(project_id: str, db: DbDep) -> list[Message]:
    return await messages_repo.list_messages(db, project_id)
