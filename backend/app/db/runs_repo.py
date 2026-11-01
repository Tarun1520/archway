"""
Saving and loading runs, and changing their status safely.

What this file does
    Creates runs, reads them back, and changes their status ONLY when the
    lifecycle rules in app/models/lifecycle.py allow it.

How it plugs in
    Called by app/api/runs.py. From Phase 2 on, the LangGraph workflow will
    call `change_status` and `mark_brief_confirmed` as a run progresses.
"""

import aiosqlite

from app.config.settings import Settings
from app.db.errors import NotFound
from app.db.projects_repo import get_project
from app.models.common import new_id, utc_now
from app.models.lifecycle import RunStatus, check_transition
from app.models.run import Run, RunStatusChange


def _to_run(row: aiosqlite.Row) -> Run:
    values = dict(row)
    # SQLite stores true/false as 1/0. Turn it back into a real bool.
    values["brief_confirmed"] = bool(values["brief_confirmed"])
    return Run(**values)


async def create_run(connection: aiosqlite.Connection, project_id: str, settings: Settings) -> Run:
    """Start a new run in `draft`, recording the service modes in force now."""
    await get_project(connection, project_id)  # raises NotFound if missing

    now = utc_now()
    run = Run(
        id=new_id(),
        project_id=project_id,
        status=RunStatus.DRAFT,
        jev_mode=settings.jev_mode,
        llm_mode=settings.llm_mode,
        github_mode=settings.github_mode,
        created_at=now,
        updated_at=now,
    )
    await connection.execute(
        """
        INSERT INTO runs (id, project_id, status, brief_confirmed,
                          jev_mode, llm_mode, github_mode, created_at, updated_at)
        VALUES (?, ?, ?, 0, ?, ?, ?, ?, ?)
        """,
        (run.id, project_id, run.status.value, run.jev_mode, run.llm_mode, run.github_mode,
         now.isoformat(), now.isoformat()),
    )
    await connection.commit()
    return run


async def get_run(connection: aiosqlite.Connection, run_id: str) -> Run:
    cursor = await connection.execute("SELECT * FROM runs WHERE id = ?", (run_id,))
    row = await cursor.fetchone()
    if row is None:
        raise NotFound("run", run_id)
    return _to_run(row)


async def list_runs(connection: aiosqlite.Connection, project_id: str) -> list[Run]:
    """A project's runs, newest first."""
    await get_project(connection, project_id)
    cursor = await connection.execute(
        "SELECT * FROM runs WHERE project_id = ? ORDER BY created_at DESC, rowid DESC", (project_id,)
    )
    return [_to_run(row) for row in await cursor.fetchall()]


async def mark_brief_confirmed(connection: aiosqlite.Connection, run_id: str) -> Run:
    """Record that the user confirmed the brief. Research may start after this.

    Phase 2's `confirm_brief` step will call this. Nothing in Phase 1's API
    does, so a Phase 1 run cannot leave `draft` by accident.
    """
    await get_run(connection, run_id)
    await connection.execute(
        "UPDATE runs SET brief_confirmed = 1, updated_at = ? WHERE id = ?",
        (utc_now().isoformat(), run_id),
    )
    await connection.commit()
    return await get_run(connection, run_id)


async def change_status(connection: aiosqlite.Connection, run_id: str, change: RunStatusChange) -> Run:
    """Move a run to a new status, or raise InvalidTransition if not allowed."""
    run = await get_run(connection, run_id)

    # The rules live in ONE place (lifecycle.py). This raises if the move is illegal.
    check_transition(
        run.status,
        change.status,
        brief_confirmed=run.brief_confirmed,
        paused_from=run.paused_from,
        outcome=change.outcome,
    )

    # Remember where a pause came from, and forget it when the pause ends.
    paused_from = run.status.value if change.status == RunStatus.PAUSED else None
    # An outcome only belongs to a completed run.
    outcome = change.outcome if change.status == RunStatus.COMPLETED else None
    outcome_note = change.outcome_note if change.status == RunStatus.COMPLETED else None

    await connection.execute(
        """
        UPDATE runs
           SET status = ?, paused_from = ?, outcome = ?, outcome_note = ?, updated_at = ?
         WHERE id = ?
        """,
        (change.status.value, paused_from, outcome, outcome_note, utc_now().isoformat(), run_id),
    )
    await connection.commit()
    return await get_run(connection, run_id)
