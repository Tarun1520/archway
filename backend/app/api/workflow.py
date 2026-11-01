"""
Workflow endpoints: starting a run and answering its questions.

    POST /api/runs/{id}/start     begin (or continue) the workflow
    POST /api/runs/{id}/clarify   answer the clarifying questions
    POST /api/runs/{id}/confirm   approve the brief, or send an edit
    GET  /api/runs/{id}/state     a full snapshot of the run
    GET  /api/runs/{id}/briefs    every saved brief version, oldest first

How a request flows
    Each POST waits while the workflow works, until it pauses for the user or
    ends, and then returns a snapshot. While it works, the progress events
    are being saved, and the browser reads them live from
    /api/runs/{id}/events (app/api/run_events.py).

    A request that does not fit the run's current step (for example
    confirming while it is still asking questions) gets HTTP 409 with the
    reason.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.api.deps import DbDep
from app.db import briefs_repo, runs_repo
from app.models.brief import ProjectBrief
from app.models.workflow import ClarifyAnswer, ConfirmDecision, RunSnapshot
from app.workflow.service import WorkflowService

router = APIRouter(prefix="/runs/{run_id}", tags=["workflow"])


def get_workflow(request: Request) -> WorkflowService:
    """The one WorkflowService that create_app() made at start-up."""
    return request.app.state.workflow


WorkflowDep = Annotated[WorkflowService, Depends(get_workflow)]


@router.post("/start")
async def start_run(run_id: str, workflow: WorkflowDep, db: DbDep) -> RunSnapshot:
    await runs_repo.get_run(db, run_id)  # 404 for an unknown run
    await workflow.start(run_id)
    return await workflow.snapshot(run_id)


@router.post("/clarify")
async def answer_questions(run_id: str, answer: ClarifyAnswer, workflow: WorkflowDep, db: DbDep) -> RunSnapshot:
    await runs_repo.get_run(db, run_id)
    await workflow.answer_clarify(run_id, answer)
    return await workflow.snapshot(run_id)


@router.post("/confirm")
async def confirm_or_edit_brief(run_id: str, decision: ConfirmDecision, workflow: WorkflowDep, db: DbDep) -> RunSnapshot:
    await runs_repo.get_run(db, run_id)
    await workflow.decide_confirm(run_id, decision)
    return await workflow.snapshot(run_id)


@router.get("/state")
async def run_state(run_id: str, workflow: WorkflowDep) -> RunSnapshot:
    return await workflow.snapshot(run_id)


@router.get("/briefs")
async def brief_versions(run_id: str, db: DbDep) -> list[ProjectBrief]:
    await runs_repo.get_run(db, run_id)
    return await briefs_repo.list_briefs(db, run_id)
