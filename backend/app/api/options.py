"""
Options endpoints (Phase 5): architecture options, choosing, revising, approving.

    GET  /api/runs/{id}/options           every option version, which passed review, what is selected / approved
    POST /api/runs/{id}/options/start     draft architecture options (after the research and its decisions)
    POST /api/runs/{id}/options/select    pick an option, or ask for a change to one (a new version)
    POST /api/runs/{id}/options/approve   approve the selected version, or ask for a change
    POST /api/runs/{id}/options/change    ask for a change to the APPROVED option (a new version; approval is not carried over)

Drafting takes a while, so those requests return at once and the browser follows progress through the run's
events (app/api/run_events.py), then reads the snapshot. A request that does not fit the run's current step
gets HTTP 409 with the reason.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import Field

from app.api.deps import DbDep
from app.db import options_repo, runs_repo
from app.models.common import ArchwayModel
from app.models.option_flow import ApprovalDecision, OptionDecision, OptionsSnapshot
from app.models.workflow import RunSnapshot
from app.workflow.service import WorkflowService

router = APIRouter(prefix="/runs/{run_id}/options", tags=["options"])


def get_workflow(request: Request) -> WorkflowService:
    return request.app.state.workflow


WorkflowDep = Annotated[WorkflowService, Depends(get_workflow)]


class ChangeRequest(ArchwayModel):
    option_id: str = Field(min_length=1)
    request: str = Field(min_length=1, max_length=1000)


@router.get("")
async def run_options(run_id: str, db: DbDep) -> OptionsSnapshot:
    await runs_repo.get_run(db, run_id)  # 404 for an unknown run
    return await options_repo.get_snapshot(db, run_id)


@router.post("/start")
async def start_options(run_id: str, workflow: WorkflowDep, db: DbDep) -> RunSnapshot:
    await runs_repo.get_run(db, run_id)
    await workflow.request_options(run_id)
    return await workflow.snapshot(run_id)


@router.post("/select")
async def select_or_revise(run_id: str, decision: OptionDecision, workflow: WorkflowDep, db: DbDep) -> RunSnapshot:
    await runs_repo.get_run(db, run_id)
    await workflow.decide_options(run_id, decision)
    return await workflow.snapshot(run_id)


@router.post("/approve")
async def approve_or_change(run_id: str, decision: ApprovalDecision, workflow: WorkflowDep, db: DbDep) -> RunSnapshot:
    await runs_repo.get_run(db, run_id)
    await workflow.decide_approval(run_id, decision)
    return await workflow.snapshot(run_id)


@router.post("/change")
async def change_approved(run_id: str, body: ChangeRequest, workflow: WorkflowDep, db: DbDep) -> RunSnapshot:
    await runs_repo.get_run(db, run_id)
    await workflow.request_change(run_id, body.option_id, body.request)
    return await workflow.snapshot(run_id)
