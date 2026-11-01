"""
Saving and reading a run's progress events.

What this file does
    Every real thing the workflow does (a step started, a brief was drafted,
    a call was made) is saved here as one numbered row.

Why events are SAVED and not just sent
    If they were only pushed to the browser, a page reload or a server
    restart would lose them. Because they are rows in the database, the
    browser can always ask "give me everything after event 41" and rebuild
    the activity feed exactly.

How it plugs in
    app/workflow/service.py writes events. app/api/run_events.py streams them.
"""

import json
from typing import Any

import aiosqlite

from app.security.scrub import scrub_data

from app.models.common import utc_now
from app.models.workflow import RunEvent


# The fields of an event that can carry text from outside services.
MESSAGE_FIELDS = {"message", "detail", "reason", "error", "summary", "about"}


async def add_event(connection: aiosqlite.Connection, run_id: str, name: str, data: dict[str, Any]) -> int:
    """Save one event and return its number.

    Events are what the browser's live stream shows, so any message in them is scrubbed of secrets first
    (app/security/scrub.py): an outside service's error text could echo part of a key.
    """
    data = {key: scrub_data(value) if key in MESSAGE_FIELDS else value for key, value in data.items()}
    cursor = await connection.execute(
        "INSERT INTO run_events (run_id, name, data, created_at) VALUES (?, ?, ?, ?)",
        (run_id, name, json.dumps(data), utc_now().isoformat()),
    )
    await connection.commit()
    return int(cursor.lastrowid)


async def events_after(connection: aiosqlite.Connection, run_id: str, after_id: int) -> list[RunEvent]:
    """Events of a run newer than `after_id`, oldest first."""
    cursor = await connection.execute(
        "SELECT * FROM run_events WHERE run_id = ? AND id > ? ORDER BY id", (run_id, after_id)
    )
    return [
        RunEvent(id=row["id"], run_id=row["run_id"], name=row["name"],
                 data=json.loads(row["data"]), created_at=row["created_at"])
        for row in await cursor.fetchall()
    ]


async def last_event_id(connection: aiosqlite.Connection, run_id: str) -> int:
    cursor = await connection.execute("SELECT COALESCE(MAX(id), 0) AS last FROM run_events WHERE run_id = ?", (run_id,))
    row = await cursor.fetchone()
    return int(row["last"])


async def source_usage(connection: aiosqlite.Connection, run_id: str) -> list[tuple[str, int, int]]:
    """(source, lookups, results) for every source this run's tools looked in, in the order the studio shows them."""
    order = ["github", "npm", "pypi", "hacker_news", "stack_overflow", "brave"]
    cursor = await connection.execute("SELECT data FROM run_events WHERE run_id = ? AND name = 'source_used'", (run_id,))
    totals: dict[str, list[int]] = {}
    for row in await cursor.fetchall():
        data = json.loads(row["data"])
        entry = totals.setdefault(str(data.get("source")), [0, 0])
        entry[0] += 1
        entry[1] += int(data.get("results") or 0)
    ranked = sorted(totals, key=lambda name: order.index(name) if name in order else len(order))
    return [(name, totals[name][0], totals[name][1]) for name in ranked]
