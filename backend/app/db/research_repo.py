"""
Saving and loading what the research team found.

What this file does
    Stores the capabilities, the proposed components, the similar projects,
    the reviewer's verdict, every message the agents sent each other, each
    inspected repository and each evidence item, and reads them back as one
    ResearchSnapshot.

Why saving is incremental
    Agents finish at different times. Each result is saved as it arrives, so
    the Research tab fills in while the team works, and a restart never loses
    what was already found.

How it plugs in
    app/workflow/service.py saves as the graph reports progress.
    app/api/research.py reads the snapshot.
"""

import json

import aiosqlite

from app.db import run_events_repo
from app.models.common import ServiceMode, utc_now
from app.models.evidence import EvidenceItem, RepoEvidence
from app.models.research import (
    Capability,
    ComponentCandidate,
    ResearchSnapshot,
    ReviewVerdict,
    SimilarProject,
    SourceUse,
    TeamMessage,
)


async def _ensure_row(connection: aiosqlite.Connection, run_id: str, mode: ServiceMode) -> None:
    await connection.execute(
        "INSERT OR IGNORE INTO research_runs (run_id, mode, updated_at) VALUES (?, ?, ?)",
        (run_id, mode, utc_now().isoformat()),
    )


async def _set(connection: aiosqlite.Connection, run_id: str, column: str, value: str, mode: ServiceMode) -> None:
    # `column` is always one of our own names below, never user input.
    await _ensure_row(connection, run_id, mode)
    await connection.execute(
        f"UPDATE research_runs SET {column} = ?, updated_at = ? WHERE run_id = ?", (value, utc_now().isoformat(), run_id)
    )
    await connection.commit()


async def save_capabilities(connection, run_id: str, capabilities: list[Capability], mode: ServiceMode) -> None:
    await _set(connection, run_id, "capabilities", json.dumps([c.model_dump(mode="json") for c in capabilities]), mode)


async def save_review(connection, run_id: str, review: ReviewVerdict, mode: ServiceMode) -> None:
    await _set(connection, run_id, "review", review.model_dump_json(), mode)


async def _upsert(connection, table: str, key_column: str, run_id: str, key: str, content: str) -> None:
    await connection.execute(
        f"INSERT INTO {table} (run_id, {key_column}, content) VALUES (?, ?, ?) "
        f"ON CONFLICT (run_id, {key_column}) DO UPDATE SET content = excluded.content",
        (run_id, key, content),
    )


async def save_components(connection, run_id: str, components: list[ComponentCandidate], mode: ServiceMode) -> None:
    await _ensure_row(connection, run_id, mode)
    for item in components:
        await _upsert(connection, "research_components", "id", run_id, item.id, item.model_dump_json())
    await connection.commit()


async def save_projects(connection, run_id: str, projects: list[SimilarProject], mode: ServiceMode) -> None:
    await _ensure_row(connection, run_id, mode)
    for item in projects:
        await _upsert(connection, "research_projects", "reference", run_id, item.facts.reference, item.model_dump_json())
    await connection.commit()


async def save_messages(connection, run_id: str, messages: list[TeamMessage], mode: ServiceMode) -> None:
    await _ensure_row(connection, run_id, mode)
    for item in messages:
        await _upsert(connection, "team_messages", "id", run_id, item.id, item.model_dump_json())
    await connection.commit()


async def save_repo(connection, run_id: str, repo: RepoEvidence) -> None:
    await _ensure_row(connection, run_id, repo.mode)
    await _upsert(connection, "repo_evidence", "repo", run_id, repo.repo, repo.model_dump_json())
    await connection.commit()


async def save_evidence(connection, run_id: str, items: list[EvidenceItem]) -> None:
    for item in items:
        await _upsert(connection, "evidence_items", "id", run_id, item.id, item.model_dump_json())
    await connection.commit()


async def add_notes(connection, run_id: str, notes: list[str], mode: ServiceMode) -> None:
    """Append visible explanations, skipping any already saved."""
    if not notes:
        return
    await _ensure_row(connection, run_id, mode)
    cursor = await connection.execute("SELECT notes FROM research_runs WHERE run_id = ?", (run_id,))
    row = await cursor.fetchone()
    existing = json.loads(row["notes"]) if row else []
    merged = existing + [note for note in dict.fromkeys(notes) if note not in existing]  # no repeats, even within one batch
    await _set(connection, run_id, "notes", json.dumps(merged), mode)


async def save_receipts(connection, run_id: str, receipts: list[dict], mode: ServiceMode) -> None:
    await _ensure_row(connection, run_id, mode)
    for item in receipts:
        await _upsert(connection, "decision_receipts", "id", run_id, item["id"], json.dumps(item))
    await connection.commit()


async def save_eligibility(connection, run_id: str, verdicts: list[dict], mode: ServiceMode) -> None:
    await _ensure_row(connection, run_id, mode)
    for item in verdicts:
        await _upsert(connection, "eligibility_results", "component_id", run_id, item["component_id"], json.dumps(item))
    await connection.commit()


async def mark_finished(connection, run_id: str, mode: ServiceMode) -> None:
    await _set(connection, run_id, "finished", "1", mode)


async def _contents(connection, table: str, run_id: str) -> list[str]:
    cursor = await connection.execute(f"SELECT content FROM {table} WHERE run_id = ? ORDER BY rowid", (run_id,))
    return [row["content"] for row in await cursor.fetchall()]


async def get_snapshot(connection: aiosqlite.Connection, run_id: str) -> ResearchSnapshot:
    """Everything saved for a run. A run with no research gives an empty snapshot."""
    cursor = await connection.execute("SELECT * FROM research_runs WHERE run_id = ?", (run_id,))
    row = await cursor.fetchone()
    if row is None:
        return ResearchSnapshot()
    return ResearchSnapshot(
        capabilities=[Capability.model_validate(c) for c in json.loads(row["capabilities"] or "[]")],
        components=[ComponentCandidate.model_validate_json(c) for c in await _contents(connection, "research_components", run_id)],
        projects=[SimilarProject.model_validate_json(c) for c in await _contents(connection, "research_projects", run_id)],
        review=ReviewVerdict.model_validate_json(row["review"]) if row["review"] else None,
        messages=[TeamMessage.model_validate_json(c) for c in await _contents(connection, "team_messages", run_id)],
        repos=[RepoEvidence.model_validate_json(c) for c in await _contents(connection, "repo_evidence", run_id)],
        evidence=[EvidenceItem.model_validate_json(c) for c in await _contents(connection, "evidence_items", run_id)],
        notes=json.loads(row["notes"]),
        eligibility=[json.loads(c) for c in await _contents(connection, "eligibility_results", run_id)],
        receipts=[json.loads(c) for c in await _contents(connection, "decision_receipts", run_id)],
        sources=[SourceUse(source=name, lookups=lookups, results=results)
                 for name, lookups, results in await run_events_repo.source_usage(connection, run_id)],
        finished=bool(int(row["finished"])),
        mode=row["mode"],
    )
