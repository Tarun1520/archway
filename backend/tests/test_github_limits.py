"""The GitHub limit bar's data: real numbers from GitHub's free /rate_limit endpoint."""

import time

import httpx
from fastapi.testclient import TestClient

from app.integrations.github_client import GitHubClient
from app.main import create_app
from tests.conftest import make_settings


async def test_the_client_reports_remaining_calls_and_seconds_until_reset():
    reset = int(time.time()) + 600

    def answer(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/rate_limit"
        return httpx.Response(200, json={"resources": {
            "core": {"limit": 60, "remaining": 0, "reset": reset},
            "search": {"limit": 10, "remaining": 7, "reset": int(time.time()) + 30},
        }})

    client = GitHubClient(mode="live", transport=httpx.MockTransport(answer))
    meters = await client.rate_limits()
    assert meters["core"]["remaining"] == 0 and 590 <= meters["core"]["seconds_until_reset"] <= 600
    assert meters["search"]["limit"] == 10


async def test_unreadable_limits_are_none_not_invented():
    client = GitHubClient(mode="live", transport=httpx.MockTransport(lambda r: httpx.Response(500, text="no")))
    assert await client.rate_limits() is None


async def test_fixture_mode_has_no_limits():
    assert await GitHubClient(mode="fixture").rate_limits() is None


def test_the_endpoint_says_unavailable_in_fixture_mode(tmp_path):
    with TestClient(create_app(make_settings(tmp_path / "data"))) as client:
        body = client.get("/api/github/limits").json()
    assert body["available"] is False and body["core"] is None and "fixture" in body["reason"]
