"""
Saving and loading brief versions.

What this file does
    Stores every version of a run's brief. A version is never overwritten
    with different content; the only change allowed to a saved version is
    marking it confirmed.

How it plugs in
    app/workflow/service.py saves a brief each time the workflow produces
    one. app/api/workflow.py reads them for the UI.
"""

import aiosqlite

from app.models.brief import ProjectBrief
from app.models.common import utc_now


async def save_brief(connection: aiosqlite.Connection, run_id: str, brief: ProjectBrief) -> None:
    """Insert this version, or update it if the same version was saved before.

    LEARNING NOTE: "ON CONFLICT ... DO UPDATE" is called an upsert. If a row
    with the same (run_id, version) exists it is updated; otherwise a new row
    is inserted. That makes saving safe to repeat.
    """
    await connection.execute(
        """
        INSERT INTO briefs (run_id, version, confirmed, content, created_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT (run_id, version) DO UPDATE SET confirmed = excluded.confirmed, content = excluded.content
        """,
        (run_id, brief.version, int(brief.confirmed), brief.model_dump_json(), utc_now().isoformat()),
    )
    await connection.commit()


async def list_briefs(connection: aiosqlite.Connection, run_id: str) -> list[ProjectBrief]:
    """Every saved version for a run, oldest first."""
    cursor = await connection.execute("SELECT content FROM briefs WHERE run_id = ? ORDER BY version", (run_id,))
    return [ProjectBrief.model_validate_json(row["content"]) for row in await cursor.fetchall()]


async def latest_brief(connection: aiosqlite.Connection, run_id: str) -> ProjectBrief | None:
    cursor = await connection.execute(
        "SELECT content FROM briefs WHERE run_id = ? ORDER BY version DESC LIMIT 1", (run_id,)
    )
    row = await cursor.fetchone()
    return ProjectBrief.model_validate_json(row["content"]) if row else None
