"""
Suggestions endpoint.

    POST /api/runs/{id}/suggestions   ideas for completing the newest draft brief

It is a POST because the first call may spend a model call. Asking again for
the same brief version returns the saved suggestions without spending.

Answers
    200  the suggestions
    404  unknown run
    409  no brief yet, brief already confirmed, or the run's call cap was reached
    502  the model service failed (the reason is in "detail"; try again)
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.api.deps import DbDep
from app.models.suggestions import BriefSuggestions
from app.workflow.suggestions_service import SuggestionService

router = APIRouter(prefix="/runs/{run_id}", tags=["suggestions"])


def get_suggestion_service(request: Request) -> SuggestionService:
    return request.app.state.suggestions


SuggestionsDep = Annotated[SuggestionService, Depends(get_suggestion_service)]


@router.post("/suggestions")
async def brief_suggestions(
    run_id: str, service: SuggestionsDep, db: DbDep, retry_standard: bool = False
) -> BriefSuggestions:
    """`?retry_standard=true` asks the model again for questions that only have generic options."""
    return await service.suggestions_for(db, run_id, retry_standard=retry_standard)
