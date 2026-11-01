"""
Run endpoints.

    POST /api/projects/{id}/runs    start a run (it begins in "draft")
    GET  /api/projects/{id}/runs    list a project's runs, newest first
    GET  /api/runs/{run_id}         get one run
    POST /api/runs/{run_id}/status  ask to move the run to another status

The status endpoint only succeeds when the lifecycle rules allow the move
(app/models/lifecycle.py). An illegal move gets HTTP 409 "Conflict" with the
reason, handled in app/main.py.

In Phase 1 nothing can confirm a brief yet, so a run cannot reach
"researching" through this API. That is deliberate: "Research cannot start
against an unconfirmed brief."
"""

import logging

from fastapi import APIRouter, status

from app.api.deps import DbDep, SettingsDep
from app.db import runs_repo
from app.models.run import Run, RunStatusChange

# Two routers because the URLs start differently (/projects/... and /runs/...).
project_runs_router = APIRouter(prefix="/projects/{project_id}/runs", tags=["runs"])
runs_router = APIRouter(prefix="/runs", tags=["runs"])
logger = logging.getLogger("archway.api")


@project_runs_router.post("", status_code=status.HTTP_201_CREATED)
async def create_run(project_id: str, db: DbDep, settings: SettingsDep) -> Run:
    run = await runs_repo.create_run(db, project_id, settings)
    logger.info(
        "run created",
        extra={"fields": {"run_id": run.id, "project_id": project_id,
                          "jev_mode": run.jev_mode, "llm_mode": run.llm_mode, "github_mode": run.github_mode}},
    )
    return run


@project_runs_router.get("")
async def list_runs(project_id: str, db: DbDep) -> list[Run]:
    return await runs_repo.list_runs(db, project_id)


@runs_router.get("/{run_id}")
async def get_run(run_id: str, db: DbDep) -> Run:
    return await runs_repo.get_run(db, run_id)


@runs_router.post("/{run_id}/status")
async def change_run_status(run_id: str, change: RunStatusChange, db: DbDep) -> Run:
    run = await runs_repo.change_status(db, run_id, change)
    logger.info("run status changed", extra={"fields": {"run_id": run.id, "status": run.status.value}})
    return run
