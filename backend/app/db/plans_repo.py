"""
Saving and loading a run's build plan (Phase 6).

What this file does
    Keeps one plan row per approved option version that a plan was asked for, and reads the run's CURRENT plan
    (the newest row) back as a PlanSnapshot, together with whether it is stale.

A plan belongs to a version
    The row is keyed by the option id and version it was built for. When a newer version is approved later, the
    snapshot says `stale`: the old plan is still shown and downloadable, labelled, until a new one is made.

How it plugs in
    app/workflow/service.py creates the row when the plan is asked for and saves what the graph reports;
    app/api/plan.py reads the snapshot, the export, and records which prompts the person marked as done.
"""

import json
from typing import Any

import aiosqlite

from app.models.common import utc_now
from app.models.option_flow import VersionRef
from app.models.plan import PlanLink, PlanSnapshot, PromptFile, Roadmap


async def start_plan(connection: aiosqlite.Connection, run_id: str, version: VersionRef) -> None:
    """A new plan for this version (a plan asked for again for the same version starts over, keeping nothing)."""
    now = utc_now().isoformat()
    await connection.execute("DELETE FROM plans WHERE run_id = ? AND option_id = ? AND version = ?", (run_id, version.id, version.version))
    await connection.execute(
        "INSERT INTO plans (run_id, option_id, version, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        (run_id, version.id, version.version, now, now),
    )
    await connection.commit()


async def _current(connection: aiosqlite.Connection, run_id: str) -> aiosqlite.Row | None:
    cursor = await connection.execute("SELECT * FROM plans WHERE run_id = ? ORDER BY created_at DESC, rowid DESC LIMIT 1", (run_id,))
    return await cursor.fetchone()


async def save_progress(connection: aiosqlite.Connection, run_id: str, changes: dict[str, Any]) -> bool:
    """Save what a plan step changed into the current plan. Returns True if anything was saved."""
    row = await _current(connection, run_id)
    if row is None:
        return False
    columns: dict[str, Any] = {}
    if changes.get("roadmap"):
        columns["roadmap"] = Roadmap.model_validate(changes["roadmap"]).model_dump_json()
    if "plan_files" in changes:
        columns["files"] = json.dumps([PromptFile.model_validate(f).model_dump(mode="json") for f in changes["plan_files"]])
    if changes.get("plan_links"):
        columns["links"] = json.dumps([PlanLink.model_validate(link).model_dump(mode="json") for link in changes["plan_links"]])
    if changes.get("plan_export"):
        columns["export"] = json.dumps(changes["plan_export"], default=str)
    if changes.get("plan_passed") is not None:
        columns["passed"] = int(bool(changes["plan_passed"]))
    if changes.get("plan_outcome"):
        columns["outcome"] = changes["plan_outcome"]
    if "plan_notes" in changes:
        columns["notes"] = json.dumps(list(dict.fromkeys(changes["plan_notes"] or [])))
    if not columns:
        return False
    columns["updated_at"] = utc_now().isoformat()
    assignments = ", ".join(f"{name} = ?" for name in columns)
    await connection.execute(
        f"UPDATE plans SET {assignments} WHERE run_id = ? AND option_id = ? AND version = ?",  # names are this file's own
        (*columns.values(), run_id, row["option_id"], row["version"]),
    )
    await connection.commit()
    return True


async def get_snapshot(connection: aiosqlite.Connection, run_id: str, approved: VersionRef | None) -> PlanSnapshot:
    row = await _current(connection, run_id)
    if row is None:
        return PlanSnapshot(approved=approved)
    built_for = VersionRef(id=row["option_id"], version=row["version"])
    return PlanSnapshot(
        requested=True, built_for=built_for, approved=approved, stale=approved != built_for,
        roadmap=Roadmap.model_validate_json(row["roadmap"]) if row["roadmap"] else None,
        files=[PromptFile.model_validate(f) for f in json.loads(row["files"])],
        links=[PlanLink.model_validate(link) for link in json.loads(row["links"])],
        passed=None if row["passed"] is None else bool(row["passed"]), outcome=row["outcome"],
        notes=json.loads(row["notes"]), completed=json.loads(row["completed"]),
    )


async def get_export(connection: aiosqlite.Connection, run_id: str) -> dict[str, Any] | None:
    row = await _current(connection, run_id)
    return json.loads(row["export"]) if row is not None and row["export"] else None


async def mark_completed(connection: aiosqlite.Connection, run_id: str, path: str, done: bool) -> list[str]:
    """Mark one prompt of the current plan as done (or not). Returns the paths marked as done."""
    row = await _current(connection, run_id)
    if row is None:
        raise LookupError("this run has no plan")
    known = {f["path"] for f in json.loads(row["files"]) if f.get("kind") == "prompt"}
    if path not in known:
        raise LookupError(f"'{path}' is not a prompt of this plan")
    completed = [p for p in json.loads(row["completed"]) if p != path] + ([path] if done else [])
    order = [f["path"] for f in json.loads(row["files"]) if f["path"] in completed]  # keep the pack's order
    await connection.execute(
        "UPDATE plans SET completed = ?, updated_at = ? WHERE run_id = ? AND option_id = ? AND version = ?",
        (json.dumps(order), utc_now().isoformat(), run_id, row["option_id"], row["version"]),
    )
    await connection.commit()
    return order
