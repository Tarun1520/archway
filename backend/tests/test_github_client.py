"""
Tests for the GitHub client, using a scripted fake GitHub.

Nothing here touches the network: httpx's MockTransport answers each request
from a function the test writes. That is also how every rule is checked
exactly: rate limits, missing READMEs, retries, caching and dates.
"""

import json
from datetime import timedelta

import httpx
import pytest

from app.models.common import utc_now
from app.integrations.cache import MemoryCache
from app.integrations.github_client import GitHubClient, GitHubError, GitHubRateLimited


def client_for(handler, **kwargs):
    slept: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        slept.append(seconds)  # remembered, never actually waited

    github = GitHubClient(mode="live", transport=httpx.MockTransport(handler), sleep=fake_sleep, **kwargs)
    return github, slept


SEARCH_REPLY = {
    "total_count": 2, "incomplete_results": False,
    "items": [
        {"full_name": "a/one", "html_url": "https://github.com/a/one", "description": "First", "language": "Python",
         "topics": ["x"], "license": {"spdx_id": "MIT", "name": "MIT License"}, "archived": False,
         "pushed_at": "2026-09-01T10:00:00Z", "stargazers_count": 50, "homepage": "https://one.example"},
        {"full_name": "b/two", "html_url": "https://github.com/b/two", "description": None, "language": None,
         "topics": [], "license": None, "archived": True, "pushed_at": None, "stargazers_count": 0, "homepage": ""},
        {"full_name": "not a valid name", "html_url": "https://github.com/x"},  # unusable: skipped
    ],
}


async def test_search_parses_results_and_keeps_unknowns_unknown():
    github, _ = client_for(lambda request: httpx.Response(200, json=SEARCH_REPLY))
    outcome = await github.search_repositories("notes")
    first, second = outcome.candidates
    assert (first.repo, first.license, first.stars, first.archived) == ("a/one", "MIT", 50, False)
    assert first.last_push is not None and first.homepage == "https://one.example"
    # GitHub reported no license, no description, no push date: all None, nothing invented.
    assert (second.license, second.description, second.last_push, second.homepage) == (None, None, None, None)
    assert len(outcome.candidates) == 2 and outcome.provenance.requested is True


async def test_requests_carry_the_documented_headers_and_the_token_only_when_set():
    seen = {}

    def handler(request):
        seen.update(request.headers)
        return httpx.Response(200, json=SEARCH_REPLY)

    github, _ = client_for(handler, token="ghp_secret_value")
    await github.search_repositories("notes")
    assert seen["accept"] == "application/vnd.github+json"
    assert seen["x-github-api-version"] == "2022-11-28"
    assert seen["authorization"] == "Bearer ghp_secret_value"

    seen.clear()
    anonymous, _ = client_for(handler)
    await anonymous.search_repositories("notes")
    assert "authorization" not in seen


async def test_a_missing_readme_is_a_fact_not_an_error():
    github, _ = client_for(lambda request: httpx.Response(404, json={"message": "Not Found"}))
    readme = await github.get_readme("a/one")
    assert (readme.found, readme.text) == (False, None)


async def test_readme_is_requested_as_raw_text():
    seen = {}

    def handler(request):
        seen["accept"] = request.headers["accept"]
        return httpx.Response(200, text="# Title\nBody")

    github, _ = client_for(handler)
    readme = await github.get_readme("a/one")
    assert seen["accept"] == "application/vnd.github.raw+json"
    assert readme.found and readme.text.startswith("# Title")


async def test_license_present_none_detected_and_null_license_object():
    github, _ = client_for(lambda r: httpx.Response(200, json={"license": {"spdx_id": "Apache-2.0", "name": "Apache License 2.0"}}))
    assert (await github.get_license("a/one")).spdx_id == "Apache-2.0"

    github, _ = client_for(lambda r: httpx.Response(404, json={"message": "Not Found"}))
    none_detected = await github.get_license("a/one")
    assert (none_detected.found, none_detected.spdx_id) == (False, None)

    github, _ = client_for(lambda r: httpx.Response(200, json={"license": None}))
    assert (await github.get_license("a/one")).found is False


async def test_a_repository_name_cannot_smuggle_a_path():
    github, _ = client_for(lambda request: httpx.Response(200, text="x"))
    for bad in ("../../user", "a/b/c", "a b/c", "a/b?x=1"):
        with pytest.raises(GitHubError):
            await github.get_readme(bad)


# --- Rate limits -----------------------------------------------------------------
async def test_primary_rate_limit_reports_the_wait_from_the_reset_header():
    reset = int(utc_now().timestamp()) + 42

    def handler(request):
        return httpx.Response(403, json={"message": "API rate limit exceeded"},
                              headers={"x-ratelimit-remaining": "0", "x-ratelimit-reset": str(reset)})

    github, _ = client_for(handler)
    with pytest.raises(GitHubRateLimited) as caught:
        await github.search_repositories("notes")
    assert 35 <= caught.value.wait_seconds <= 45


async def test_secondary_rate_limit_uses_retry_after_then_a_minute():
    github, _ = client_for(lambda r: httpx.Response(429, json={"message": "slow down"}, headers={"retry-after": "7"}))
    with pytest.raises(GitHubRateLimited) as caught:
        await github.search_repositories("notes")
    assert caught.value.wait_seconds == 7

    github, _ = client_for(lambda r: httpx.Response(403, json={"message": "You have exceeded a secondary rate limit"}))
    with pytest.raises(GitHubRateLimited) as caught:
        await github.search_repositories("notes")
    assert caught.value.wait_seconds == 60


async def test_a_plain_forbidden_is_an_error_not_a_rate_limit():
    github, _ = client_for(lambda r: httpx.Response(403, json={"message": "Resource not accessible"}))
    with pytest.raises(GitHubError) as caught:
        await github.search_repositories("notes")
    assert not isinstance(caught.value, GitHubRateLimited)


# --- Failures and retries --------------------------------------------------------
async def test_temporary_failures_are_retried_with_waits_then_succeed():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(502) if calls["n"] < 3 else httpx.Response(200, json=SEARCH_REPLY)

    github, slept = client_for(handler)
    outcome = await github.search_repositories("notes")
    assert calls["n"] == 3 and slept == [0.5, 1.0] and len(outcome.candidates) == 2


async def test_retries_are_bounded_and_the_failure_is_reported():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        raise httpx.ConnectError("boom")

    github, _ = client_for(handler)
    with pytest.raises(GitHubError, match="tried 3 times"):
        await github.search_repositories("notes")
    assert calls["n"] == 3


async def test_a_bad_request_is_not_retried():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(422, json={"message": "Validation Failed"})

    github, _ = client_for(handler)
    with pytest.raises(GitHubError, match="422"):
        await github.search_repositories("notes")
    assert calls["n"] == 1


async def test_a_token_never_appears_in_an_error_message():
    github, _ = client_for(lambda r: httpx.Response(401, json={"message": "Bad credentials"}), token="ghp_topsecret")
    with pytest.raises(GitHubError) as caught:
        await github.search_repositories("notes")
    assert "ghp_topsecret" not in str(caught.value)


# --- The cache -------------------------------------------------------------------
async def test_a_cached_answer_keeps_its_original_retrieval_date_and_costs_no_request():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(200, text="# README")

    github, _ = client_for(handler, cache=MemoryCache())
    first = await github.get_readme("a/one")
    second = await github.get_readme("a/one")

    assert calls["n"] == 1
    assert first.provenance.requested is True and first.provenance.from_cache is False
    assert second.provenance.requested is False and second.provenance.from_cache is True
    assert second.provenance.retrieved_at == first.provenance.retrieved_at  # the ORIGINAL date


async def test_an_expired_cache_entry_is_fetched_again_with_a_new_date():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(200, text="# README")

    cache = MemoryCache(ttl=timedelta(seconds=-1))  # everything is already expired
    github, _ = client_for(handler, cache=cache)
    await github.get_readme("a/one")
    again = await github.get_readme("a/one")
    assert calls["n"] == 2 and again.provenance.from_cache is False


async def test_errors_and_rate_limits_are_never_cached():
    state = {"limited": True}

    def handler(request):
        if state["limited"]:
            return httpx.Response(429, headers={"retry-after": "1"})
        return httpx.Response(200, text="# README")

    github, _ = client_for(handler, cache=MemoryCache())
    with pytest.raises(GitHubRateLimited):
        await github.get_readme("a/one")
    state["limited"] = False
    assert (await github.get_readme("a/one")).found is True


async def test_live_searches_are_spaced_out_so_the_rate_limit_is_not_hit():
    import httpx

    from app.integrations.github_client import GitHubClient, SEARCH_GAP_WITHOUT_TOKEN

    waits: list[float] = []

    async def record(seconds):
        waits.append(seconds)

    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={"items": []}))
    client = GitHubClient(mode="live", transport=transport, sleep=record)
    await client.search_repositories("one two")
    await client.search_repositories("three four")
    assert len(waits) == 1 and 0 < waits[0] <= SEARCH_GAP_WITHOUT_TOKEN  # the second search waited for its turn
