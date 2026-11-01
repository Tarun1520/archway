"""
The live-progress stream of a real run, sent as server-sent events.

    GET /api/runs/{id}/events?after=N    events newer than number N, then live

What this file does
    Sends the run's saved events to the browser, oldest first, and then keeps
    the connection open and sends new ones as they are saved.

How "live" works here
    The workflow writes each event to the database as it happens
    (app/workflow/service.py). This endpoint simply checks the database for
    newer rows a few times a second. It is not the fanciest design, but it is
    easy to follow and it has a useful property: nothing is ever lost. After
    a page reload, a dropped connection, or a backend restart, the browser
    asks for "everything after the last number I saw" and catches up.

LEARNING NOTE: Last-Event-ID
    Each event is sent with its number as the SSE `id`. When a browser's
    EventSource reconnects by itself, it sends that number back in a header
    called Last-Event-ID, so the stream can continue where it stopped.

Learn more: LEARNING_GUIDE.md topics 12 and 34.
"""

import asyncio
from collections.abc import AsyncIterable
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.sse import EventSourceResponse, ServerSentEvent

from app.api.deps import DbDep, SettingsDep
from app.db import run_events_repo, runs_repo
from app.db.connection import open_connection

router = APIRouter(tags=["workflow"])

POLL_SECONDS = 0.25  # how often to look for new events


async def run_must_exist(run_id: str, db: DbDep) -> None:
    """Answer 404 for an unknown run BEFORE the stream starts.

    LEARNING NOTE: once a stream has begun, the "200 OK" status has already
    been sent and cannot be changed. A dependency runs before the endpoint,
    so this is the place for checks that may need to refuse the request.
    """
    await runs_repo.get_run(db, run_id)


@router.get("/runs/{run_id}/events", response_class=EventSourceResponse, dependencies=[Depends(run_must_exist)])
async def stream_run_events(
    run_id: str,
    request: Request,
    settings: SettingsDep,
    after: Annotated[int, Query(ge=0)] = 0,
    # follow=false sends what exists and closes. Used by tests and by tools.
    follow: bool = True,
    last_event_id: Annotated[str | None, Header()] = None,
) -> AsyncIterable[ServerSentEvent]:
    # A reconnecting browser reports the last event it saw; that wins over `after`.
    if last_event_id and last_event_id.isdigit():
        after = max(after, int(last_event_id))

    async with open_connection(settings.database_path) as db:
        while True:
            for event in await run_events_repo.events_after(db, run_id, after):
                after = event.id
                yield ServerSentEvent(event=event.name, data=event.data, id=str(event.id))

            if not follow or await request.is_disconnected():
                return
            await asyncio.sleep(POLL_SECONDS)
