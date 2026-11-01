"""
Saving and counting calls to outside services.

How it plugs in
    app/workflow/service.py records one UsageEvent per model call.
    The totals feed the usage counters in the UI.
"""

import aiosqlite

from app.models.usage import UsageEvent


async def add_usage(connection: aiosqlite.Connection, event: UsageEvent) -> None:
    await connection.execute(
        "INSERT INTO usage_events (run_id, service, mode, count, tokens_if_known, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
        (event.run_id, event.service, event.mode, event.count, event.tokens_if_known, event.timestamp.isoformat()),
    )
    await connection.commit()


async def calls_by_service(connection: aiosqlite.Connection, run_id: str) -> dict[str, int]:
    """How many calls a run has made to each service, e.g. {"llm": 2}."""
    cursor = await connection.execute(
        "SELECT service, SUM(count) AS calls FROM usage_events WHERE run_id = ? GROUP BY service", (run_id,)
    )
    return {row["service"]: int(row["calls"]) for row in await cursor.fetchall()}
