"""
Lesson 10: FastAPI and server-sent events (SSE)
===============================================

What you learn here
    - FastAPI turns a Python function into an HTTP endpoint (a URL the
      frontend can call).
    - A normal endpoint answers once. An SSE endpoint keeps the connection
      open and sends many small events over time, one direction only:
      server -> browser. That is all a progress feed needs.

How to run (from the project root)
    backend/.venv/bin/python backend/learning/10_fastapi_and_sse.py

    This lesson does NOT start a real server. It uses FastAPI's TestClient,
    which calls the app directly inside this process. Tests do the same.

Where Archway uses this
    backend/app/api/ holds the real routes. The run-events endpoint will
    forward LangGraph's stream (Lesson 06) to the browser exactly like the
    `/runs/demo/events` endpoint below forwards a pretend one.
"""

import asyncio
from collections.abc import AsyncIterable

from fastapi import FastAPI
from fastapi.sse import EventSourceResponse, ServerSentEvent
from fastapi.testclient import TestClient
from pydantic import BaseModel

app = FastAPI(title="Lesson 10 demo")


# -----------------------------------------------------------------------------
# A normal endpoint: one request, one answer
# -----------------------------------------------------------------------------
class Health(BaseModel):
    status: str
    jev_mode: str


# LEARNING NOTE: the decorator
#   `@app.get("/health")` registers the function below for GET /health.
#   Because the return type is a Pydantic model, FastAPI converts it to JSON
#   and checks its shape for us.
@app.get("/health")
async def health() -> Health:
    return Health(status="ok", jev_mode="fixture")


# -----------------------------------------------------------------------------
# An SSE endpoint: one request, a stream of events
# -----------------------------------------------------------------------------
# DEMO DATA: these events are made up for the lesson.
DEMO_EVENTS = [
    ("node_started", {"node": "github_search"}),
    ("activity", {"message": "GitHub: 14 candidates retrieved"}),
    ("node_finished", {"node": "github_search"}),
]


# LEARNING NOTE: how an endpoint becomes a stream
#   Two things make this SSE instead of a normal answer:
#     1. response_class=EventSourceResponse
#     2. the function uses `yield` instead of `return`
#   Every `yield` sends one event to the browser straight away.
@app.get("/runs/demo/events", response_class=EventSourceResponse)
async def demo_events() -> AsyncIterable[ServerSentEvent]:
    for event_name, data in DEMO_EVENTS:
        await asyncio.sleep(0.05)  # pretend some work happened in between
        yield ServerSentEvent(event=event_name, data=data)


if __name__ == "__main__":
    client = TestClient(app)

    print("1. Normal endpoint: GET /health")
    response = client.get("/health")
    print("   status code:", response.status_code)
    print("   body       :", response.json())

    print("\n2. SSE endpoint: GET /runs/demo/events")
    with client.stream("GET", "/runs/demo/events") as stream:
        print("   content-type:", stream.headers["content-type"])
        print("   raw lines exactly as they travel over the connection:")
        for line in stream.iter_lines():
            # Each event is an "event:" line, a "data:" line, then a blank line.
            print("     |", line)
