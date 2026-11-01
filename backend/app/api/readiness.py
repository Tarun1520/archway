"""
Is a project's description enough to draft a brief?

    GET /api/projects/{id}/readiness   {"ready": true|false, "reason": "..."}

The studio asks this after each saved message, to lock "Create brief" (and say
why) until there is something specific to work from. The rule itself is plain
code in app/policy/idea_readiness.py; starting a run checks the same rule, so
the lock cannot be bypassed.
"""

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.api.deps import DbDep
from app.db import messages_repo, projects_repo
from app.policy.idea_readiness import idea_readiness

router = APIRouter(prefix="/projects/{project_id}/readiness", tags=["projects"])
# The same rule on text that is not saved yet (Archy checks what was spoken before offering a brief).
check_router = APIRouter(prefix="/readiness", tags=["projects"])


class ReadinessOut(BaseModel):
    ready: bool
    reason: str | None


class ReadinessCheckIn(BaseModel):
    texts: list[str] = Field(max_length=50)


@router.get("")
async def project_readiness(project_id: str, db: DbDep) -> ReadinessOut:
    await projects_repo.get_project(db, project_id)  # 404 for an unknown project
    messages = await messages_repo.list_messages(db, project_id)
    result = idea_readiness([message.content for message in messages if message.role == "user"])
    return ReadinessOut(ready=result.ready, reason=result.reason)


@check_router.post("")
async def check_text(body: ReadinessCheckIn) -> ReadinessOut:
    """Is this description (one or more pieces of text) enough? Nothing is saved."""
    result = idea_readiness([text[:4000] for text in body.texts])
    return ReadinessOut(ready=result.ready, reason=result.reason)
