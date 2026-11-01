"""
Plan endpoints (Phase 6): the roadmap, the prompt pack, marking prompts done, and the downloads.

    GET  /api/runs/{id}/plan                          the current plan (tasks, decisions, files and their checks, links)
    POST /api/runs/{id}/plan/start                    make the build plan for the approved option version
    POST /api/runs/{id}/plan/prompts/complete         mark one prompt as done (or not done)
    GET  /api/runs/{id}/plan/export.zip               build-pack/ with every file, plan.json and PLAN.md
    GET  /api/runs/{id}/plan/export.json              the whole plan as data
    GET  /api/runs/{id}/plan/export.md                the whole plan as one readable document

Planning takes a little while, so /start returns at once and the browser follows the run's events (plan_updated),
then reads the plan. A request that does not fit the run's current step gets HTTP 409 with the reason.
"""

import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse, Response
from pydantic import Field

from app.api.deps import DbDep
from app.db import options_repo, plans_repo, runs_repo
from app.models.common import ArchwayModel
from app.models.plan import PlanSnapshot
from app.models.workflow import RunSnapshot
from app.promptgen.export import pack_zip, plan_markdown
from app.workflow.service import WorkflowService

router = APIRouter(prefix="/runs/{run_id}/plan", tags=["plan"])


def get_workflow(request: Request) -> WorkflowService:
    return request.app.state.workflow


WorkflowDep = Annotated[WorkflowService, Depends(get_workflow)]


class PromptDone(ArchwayModel):
    path: str = Field(min_length=1, max_length=200)
    done: bool


async def _snapshot(db, run_id: str) -> PlanSnapshot:
    await runs_repo.get_run(db, run_id)  # 404 for an unknown run
    options = await options_repo.get_snapshot(db, run_id)
    return await plans_repo.get_snapshot(db, run_id, options.approved)


async def _exported(db, run_id: str) -> tuple[PlanSnapshot, dict]:
    plan = await _snapshot(db, run_id)
    data = await plans_repo.get_export(db, run_id)
    if data is None:
        raise HTTPException(status_code=404, detail="this run has no exported plan yet")
    return plan, data


def _filename(run_id: str, plan: PlanSnapshot, extension: str) -> str:
    version = f"{plan.built_for.id}-v{plan.built_for.version}" if plan.built_for else "plan"
    return f"archway-{run_id[:8]}-{version}.{extension}"


@router.get("")
async def run_plan(run_id: str, db: DbDep) -> PlanSnapshot:
    return await _snapshot(db, run_id)


@router.post("/start")
async def start_plan(run_id: str, workflow: WorkflowDep, db: DbDep) -> RunSnapshot:
    await runs_repo.get_run(db, run_id)
    await workflow.request_plan(run_id)
    return await workflow.snapshot(run_id)


@router.post("/prompts/complete")
async def complete_prompt(run_id: str, body: PromptDone, db: DbDep) -> PlanSnapshot:
    await runs_repo.get_run(db, run_id)
    try:
        await plans_repo.mark_completed(db, run_id, body.path, body.done)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return await _snapshot(db, run_id)


@router.get("/export.zip")
async def export_zip(run_id: str, db: DbDep) -> Response:
    plan, data = await _exported(db, run_id)
    return Response(
        content=pack_zip(plan, data), media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{_filename(run_id, plan, "zip")}"'},
    )


@router.get("/export.json")
async def export_json(run_id: str, db: DbDep) -> Response:
    plan, data = await _exported(db, run_id)
    return Response(
        content=json.dumps(data, indent=2, ensure_ascii=False, default=str), media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{_filename(run_id, plan, "json")}"'},
    )


@router.get("/export.md")
async def export_markdown(run_id: str, db: DbDep) -> PlainTextResponse:
    plan, data = await _exported(db, run_id)
    return PlainTextResponse(
        plan_markdown(data), media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{_filename(run_id, plan, "md")}"'},
    )
