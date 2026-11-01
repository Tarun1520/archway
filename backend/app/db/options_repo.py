"""
Saving and loading a run's architecture options.

What this file does
    Keeps every option VERSION (with its review and whether it was approved) and the small options state of a
    run, and reads them back as one OptionsSnapshot.

Approval belongs to a version
    `approved` is stored on the version that was approved. When a newer version of that option exists, the
    approval is superseded: the snapshot's `approved` is then empty. A revision never inherits approval.

How it plugs in
    app/workflow/service.py saves as the graph reports progress; app/api/options.py reads the snapshot.
"""

import json
from typing import Any

import aiosqlite

from app.models.common import utc_now
from app.models.option import ArchitectureOption
from app.models.option_flow import OptionsSnapshot, VersionRef
from app.options.versions import latest, presented


async def _ensure_row(connection: aiosqlite.Connection, run_id: str) -> None:
    await connection.execute("INSERT OR IGNORE INTO option_state (run_id, updated_at) VALUES (?, ?)", (run_id, utc_now().isoformat()))


async def mark_requested(connection: aiosqlite.Connection, run_id: str) -> None:
    await _ensure_row(connection, run_id)
    await connection.execute("UPDATE option_state SET requested = 1, updated_at = ? WHERE run_id = ?", (utc_now().isoformat(), run_id))
    await connection.commit()


async def save_options(connection: aiosqlite.Connection, run_id: str, options: list[dict[str, Any]]) -> None:
    """Save every version in the list (new ones are added; existing ones are rewritten, e.g. when approved)."""
    await _ensure_row(connection, run_id)
    for option in options:
        content = ArchitectureOption.model_validate(option).model_dump_json()  # refuses a malformed option
        await connection.execute(
            "INSERT INTO option_versions (run_id, id, version, content) VALUES (?, ?, ?, ?) "
            "ON CONFLICT (run_id, id, version) DO UPDATE SET content = excluded.content",
            (run_id, option["id"], option["version"], content),
        )
    await connection.commit()


_UNCHANGED: Any = object()  # "leave this field as it is" (None is a real value: "nothing selected")


async def save_state(
    connection: aiosqlite.Connection, run_id: str, *, selected: Any = _UNCHANGED, notes: list[str] | None = None,
    no_recommendation: Any = _UNCHANGED,
) -> None:
    """Update only the fields given: a step that changed the selection does not touch the notes."""
    await _ensure_row(connection, run_id)
    if selected is not _UNCHANGED:
        await connection.execute("UPDATE option_state SET selected_option_id = ? WHERE run_id = ?", (selected, run_id))
    if no_recommendation is not _UNCHANGED:
        await connection.execute("UPDATE option_state SET no_recommendation = ? WHERE run_id = ?", (int(bool(no_recommendation)), run_id))
    if notes:
        cursor = await connection.execute("SELECT notes FROM option_state WHERE run_id = ?", (run_id,))
        existing = json.loads((await cursor.fetchone())["notes"])
        merged = existing + [note for note in dict.fromkeys(notes) if note not in existing]
        await connection.execute("UPDATE option_state SET notes = ? WHERE run_id = ?", (json.dumps(merged), run_id))
    await connection.execute("UPDATE option_state SET updated_at = ? WHERE run_id = ?", (utc_now().isoformat(), run_id))
    await connection.commit()


async def get_snapshot(connection: aiosqlite.Connection, run_id: str) -> OptionsSnapshot:
    cursor = await connection.execute("SELECT * FROM option_state WHERE run_id = ?", (run_id,))
    state = await cursor.fetchone()
    if state is None:
        return OptionsSnapshot()
    cursor = await connection.execute("SELECT content FROM option_versions WHERE run_id = ? ORDER BY rowid", (run_id,))
    options = [ArchitectureOption.model_validate_json(row["content"]) for row in await cursor.fetchall()]
    dicts = [o.model_dump(mode="json") for o in options]
    shown = presented(dicts)
    newest = {o["id"]: o["version"] for o in latest(dicts)}
    approved = next((VersionRef(id=o["id"], version=o["version"]) for o in dicts if o["approved"] and newest[o["id"]] == o["version"]), None)
    selected_id = state["selected_option_id"]
    selected = next((VersionRef(id=o["id"], version=o["version"]) for o in shown if o["id"] == selected_id), None)
    return OptionsSnapshot(
        requested=bool(state["requested"]), options=options,
        presented=[VersionRef(id=o["id"], version=o["version"]) for o in shown],
        selected=selected, approved=approved, notes=json.loads(state["notes"]), no_recommendation=bool(state["no_recommendation"]),
    )
