"""
Tests for the HTTP API (app/api/), through a real FastAPI test client.

Checkpoint 1 items covered here:
    - "Projects survive a backend restart" (through the API this time)
    - "Mock data is labeled as demo data"
    - "LIVE/FIXTURE badge is visible" (the data the badge is drawn from)
"""

import json

from fastapi.testclient import TestClient

from app.main import create_app


def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_config_reports_modes_badge_and_caps(client):
    body = client.get("/api/config").json()
    assert body["modes"]["badge"] == "FIXTURE"
    assert body["modes"]["label"] == "FIXTURE MODE: jev, llm, github"
    assert body["caps"] == {"max_llm_calls_per_run": 5, "max_jev_calls_per_run": 5, "max_github_calls_per_run": 90}


# --- Projects ---------------------------------------------------------------------
def test_create_get_list_rename_and_delete_a_project(client):
    created = client.post("/api/projects", json={"name": "Notes app", "idea": "search my notes"})
    assert created.status_code == 201
    project = created.json()
    assert project["idea"] == "search my notes"

    assert client.get(f"/api/projects/{project['id']}").json() == project
    assert [p["id"] for p in client.get("/api/projects").json()] == [project["id"]]

    renamed = client.patch(f"/api/projects/{project['id']}", json={"name": "Notes"})
    assert renamed.json()["name"] == "Notes"

    assert client.delete(f"/api/projects/{project['id']}").status_code == 204
    assert client.get(f"/api/projects/{project['id']}").status_code == 404


def test_a_project_without_an_idea_reports_null_not_an_empty_string(client):
    project = client.post("/api/projects", json={"name": "Blank"}).json()
    assert project["idea"] is None


def test_bad_input_is_rejected_with_422(client):
    assert client.post("/api/projects", json={"name": ""}).status_code == 422
    assert client.post("/api/projects", json={"name": "ok", "idea": "x" * 2001}).status_code == 422
    # A client cannot choose its own id: unknown fields are refused.
    assert client.post("/api/projects", json={"name": "ok", "id": "mine"}).status_code == 422


def test_unknown_ids_give_404(client):
    assert client.get("/api/projects/nope").status_code == 404
    assert client.get("/api/runs/nope").status_code == 404
    assert client.post("/api/projects/nope/messages", json={"content": "hi"}).status_code == 404


def test_projects_survive_a_backend_restart(settings):
    with TestClient(create_app(settings)) as first_server:
        project = first_server.post("/api/projects", json={"name": "Survivor"}).json()
        first_server.post(f"/api/projects/{project['id']}/messages", json={"content": "remember me"})
        # Adding a message updates the project's "last changed" time, so read
        # the project again to know exactly what was saved before the restart.
        project = first_server.get(f"/api/projects/{project['id']}").json()

    # A completely new app object, as after stopping and starting the server.
    with TestClient(create_app(settings)) as second_server:
        assert second_server.get(f"/api/projects/{project['id']}").json() == project
        messages = second_server.get(f"/api/projects/{project['id']}/messages").json()
        assert [m["content"] for m in messages] == ["remember me"]


# --- Messages ---------------------------------------------------------------------
def test_add_and_list_messages(client):
    project = client.post("/api/projects", json={"name": "Chat"}).json()
    url = f"/api/projects/{project['id']}/messages"
    assert client.post(url, json={"content": "first"}).status_code == 201
    client.post(url, json={"role": "assistant", "content": "second"})
    listed = client.get(url).json()
    assert [(m["role"], m["content"]) for m in listed] == [("user", "first"), ("assistant", "second")]


# --- Runs -------------------------------------------------------------------------
def test_a_run_starts_as_a_draft_and_cannot_start_research_unconfirmed(client):
    project = client.post("/api/projects", json={"name": "P"}).json()
    run = client.post(f"/api/projects/{project['id']}/runs").json()
    assert run["status"] == "draft"
    assert run["jev_mode"] == "fixture"

    refused = client.post(f"/api/runs/{run['id']}/status", json={"status": "researching"})
    assert refused.status_code == 409
    assert "before the brief is confirmed" in refused.json()["detail"]
    assert client.get(f"/api/runs/{run['id']}").json()["status"] == "draft"


def test_a_run_can_be_paused_resumed_and_cancelled(client):
    project = client.post("/api/projects", json={"name": "P"}).json()
    run = client.post(f"/api/projects/{project['id']}/runs").json()
    url = f"/api/runs/{run['id']}/status"

    paused = client.post(url, json={"status": "paused"}).json()
    assert (paused["status"], paused["paused_from"]) == ("paused", "draft")
    assert client.post(url, json={"status": "draft"}).json()["status"] == "draft"
    assert client.post(url, json={"status": "cancelled"}).json()["status"] == "cancelled"
    # Cancelled is terminal.
    assert client.post(url, json={"status": "draft"}).status_code == 409
    assert [r["id"] for r in client.get(f"/api/projects/{project['id']}/runs").json()] == [run["id"]]


# --- Demo data is labelled --------------------------------------------------------
def test_sample_briefs_are_all_labelled_as_demo_data(client):
    samples = client.get("/api/sample-briefs").json()
    assert 6 <= len(samples) <= 8
    assert all(sample["demo"] is True for sample in samples)


def read_sse(response) -> list[dict]:
    """Turn the raw event-stream text into a list of {"event", "id", "data"}."""
    events, current = [], {}
    for line in response.iter_lines():
        if line == "":  # a blank line ends one event
            if current:
                events.append(current)
                current = {}
            continue
        name, _, value = line.partition(": ")
        current[name] = json.loads(value) if name == "data" else value
    return events


def test_demo_event_stream_is_sse_and_every_event_is_labelled_demo(client):
    with client.stream("GET", "/api/demo/events", params={"delay_ms": 0}) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        events = read_sse(response)

    assert events[0]["event"] == "demo_notice"
    assert events[-1]["event"] == "stream_finished"
    assert all(event["data"]["demo"] is True for event in events)
    assert [event["id"] for event in events] == [str(n) for n in range(1, len(events) + 1)]


def test_demo_stream_delay_is_bounded(client):
    assert client.get("/api/demo/events", params={"delay_ms": 999999}).status_code == 422
