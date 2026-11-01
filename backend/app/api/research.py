"""
Research endpoint.

    GET /api/runs/{id}/research   everything the research stage found for a run

What it returns
    The plan, the candidates, the shortlist, each inspected repository with
    its provenance (address and retrieval time), the evidence items with
    short excerpts, and the visible notes about anything partial. A run that
    has not researched yet returns an empty snapshot, not an error.
"""

from fastapi import APIRouter

from app.api.deps import DbDep
from app.db import research_repo, runs_repo
from app.models.research import ResearchSnapshot

router = APIRouter(prefix="/runs/{run_id}", tags=["research"])


@router.get("/research")
async def run_research(run_id: str, db: DbDep) -> ResearchSnapshot:
    await runs_repo.get_run(db, run_id)  # 404 for an unknown run
    return await research_repo.get_snapshot(db, run_id)
