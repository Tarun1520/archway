"""
Saving and loading suggestions for a brief version.

How it plugs in
    app/workflow/suggestions_service.py asks here before calling the model,
    and saves what it gets.
"""

import aiosqlite

from app.models.common import utc_now
from app.models.suggestions import BriefSuggestions


async def get_suggestions(connection: aiosqlite.Connection, run_id: str, brief_version: int) -> BriefSuggestions | None:
    cursor = await connection.execute(
        "SELECT content FROM brief_suggestions WHERE run_id = ? AND brief_version = ?", (run_id, brief_version)
    )
    row = await cursor.fetchone()
    return BriefSuggestions.model_validate_json(row["content"]) if row else None


async def save_suggestions(connection: aiosqlite.Connection, run_id: str, suggestions: BriefSuggestions) -> None:
    await connection.execute(
        """
        INSERT INTO brief_suggestions (run_id, brief_version, content, created_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT (run_id, brief_version) DO UPDATE SET content = excluded.content
        """,
        (run_id, suggestions.brief_version, suggestions.model_dump_json(), utc_now().isoformat()),
    )
    await connection.commit()
