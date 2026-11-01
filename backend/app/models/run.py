"""
Run: one pass of the Archway workflow for a project.

What this file does
    Defines the stored run and the request body used to change its status.
    A run remembers which service modes it was started with, so a result
    can always say whether it came from live calls or fixtures.

How it plugs in
    app/db/runs_repo.py saves and loads `Run` and enforces the lifecycle
    rules from app/models/lifecycle.py.
    From Phase 2 on, a run's id is also its LangGraph `thread_id`.
"""

from datetime import datetime

from app.models.common import ArchwayModel, ServiceMode
from app.models.lifecycle import RunOutcome, RunStatus


class Run(ArchwayModel):
    id: str
    project_id: str

    status: RunStatus
    paused_from: RunStatus | None = None  # set only while status is "paused"
    brief_confirmed: bool = False  # research cannot start until this is True

    outcome: RunOutcome | None = None  # set when the run completes
    outcome_note: str | None = None  # the visible explanation for a partial result

    # The modes this run was started with. Fixed for the life of the run.
    jev_mode: ServiceMode
    llm_mode: ServiceMode
    github_mode: ServiceMode

    created_at: datetime
    updated_at: datetime


class RunStatusChange(ArchwayModel):
    """Request body: ask for a run to move to a new status."""

    status: RunStatus
    outcome: RunOutcome | None = None
    outcome_note: str | None = None
