"""
Demo live-progress stream (DEMO DATA), sent as server-sent events.

    GET /api/demo/events   a short scripted sequence of workflow events

What this file does
    Streams the made-up events from app/events/demo_events.py one at a time,
    so the frontend's live workflow view and activity feed can be built
    before the real workflow exists. Every event says "demo": true.

LEARNING NOTE: how an endpoint becomes a stream
    1. response_class=EventSourceResponse
    2. `yield` instead of `return`
    Each `yield` sends one event to the browser immediately and keeps the
    connection open (LEARNING_GUIDE.md topic 34, lesson 10).

What changes in Phase 2
    A new endpoint, /api/runs/{run_id}/events, will yield the events of a
    real LangGraph run. This demo endpoint stays for development and tests.
"""

import asyncio
from collections.abc import AsyncIterable
from typing import Annotated

from fastapi import APIRouter, Query
from fastapi.sse import EventSourceResponse, ServerSentEvent

from app.events.demo_events import demo_events

router = APIRouter(tags=["demo"])


@router.get("/demo/events", response_class=EventSourceResponse)
async def stream_demo_events(
    # The pause between events, so a person can watch them arrive. Tests pass 0.
    # ge / le = allowed range, so nobody can ask the server to wait forever.
    delay_ms: Annotated[int, Query(ge=0, le=5000)] = 600,
) -> AsyncIterable[ServerSentEvent]:
    for position, (event_name, data) in enumerate(demo_events(), start=1):
        if delay_ms:
            await asyncio.sleep(delay_ms / 1000)
        # `id` numbers the events. A browser that reconnects reports the last
        # id it saw, which real streams can use to avoid repeating events.
        yield ServerSentEvent(event=event_name, data=data, id=str(position))
