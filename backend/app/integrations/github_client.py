"""
GitHubClient: the one place that talks to the GitHub REST API.

What this file does
    Three questions, each one HTTP request:
        search_repositories(query)   GET /search/repositories
        get_readme(owner/name)       GET /repos/{owner}/{name}/readme
        get_license(owner/name)      GET /repos/{owner}/{name}/license

What was verified against GitHub's documentation (2026-10-14)
    - Search returns {total_count, incomplete_results, items}. Each item has
      full_name, html_url, description, language, topics, license (an object
      with spdx_id, or null), archived, pushed_at, stargazers_count, homepage.
    - The README endpoint answers 404 when there is none, and returns the raw
      text when asked with  Accept: application/vnd.github.raw+json
    - The license endpoint answers 404 when no license file is detected.
    - Rate limits: the headers x-ratelimit-remaining / x-ratelimit-reset tell
      you the budget; exceeding it gives 403 or 429. A secondary limit may
      send retry-after, or give no headers, in which case wait a minute.
    - Search has its own, lower limit (30 per minute with a token, 10
      without), so limits are read from responses, never hard-coded.

The honesty rules built in
    - A failed request is returned or raised as an error. It is never turned
      into an empty-looking result.
    - "GitHub says there is no README" (404) is a real answer. "We could not
      reach GitHub" is not. They are different outcomes here.
    - Cached answers keep their original retrieval date.

How it plugs in
    app/research/factory.py builds the client (live or fixture) from settings.
    The research nodes receive it through the run context.

Learn more: LEARNING_GUIDE.md topics 17, 33, 36 and 42.
"""

import asyncio
import json
import re
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx

from app.security.scrub import scrub

from app.models.common import ServiceMode, utc_now
from app.models.research import Candidate
from app.integrations.cache import CachedResponse, NoCache, ResponseCache, cache_key

GITHUB_API = "https://api.github.com"
API_VERSION = "2022-11-28"
MAX_ATTEMPTS = 3
MAX_README_CHARS = 200_000  # a README longer than this is cut, and said to be cut
FULL_NAME = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")

Sleep = Callable[[float], Awaitable[None]]


class GitHubError(Exception):
    """A request failed. The message is safe to show: it never contains a token."""


class GitHubRateLimited(GitHubError):
    """GitHub said to slow down."""

    def __init__(self, message: str, wait_seconds: float):
        super().__init__(message)
        self.wait_seconds = wait_seconds


@dataclass(frozen=True)
class Provenance:
    """Where an answer came from. Every result carries one."""

    retrieved_at: datetime  # for a cached answer, the ORIGINAL fetch time
    from_cache: bool
    requested: bool  # True when a real request was sent (counts as a call)


@dataclass(frozen=True)
class SearchOutcome:
    candidates: list[Candidate]
    incomplete: bool  # GitHub says the search hit its time limit: results may be partial
    provenance: Provenance


@dataclass(frozen=True)
class ReadmeOutcome:
    # None with found=False means GitHub reported no README for this repository.
    text: str | None
    found: bool
    truncated: bool
    html_url: str | None
    provenance: Provenance


@dataclass(frozen=True)
class LicenseOutcome:
    spdx_id: str | None  # None with found=False means no license file was detected
    name: str | None
    found: bool
    provenance: Provenance


def _wait_for_rate_limit(response: httpx.Response, body_text: str) -> float | None:
    """How long to wait if this response is a rate limit, otherwise None."""
    if response.status_code not in (403, 429):
        return None
    headers = response.headers
    remaining = headers.get("x-ratelimit-remaining")
    retry_after = headers.get("retry-after")
    message = body_text.lower()
    is_limit = response.status_code == 429 or remaining == "0" or retry_after is not None or "rate limit" in message
    if not is_limit:
        return None  # a plain 403 (for example "forbidden"), not a rate limit

    if retry_after is not None:
        try:
            return max(0.0, float(retry_after))
        except ValueError:
            pass
    reset = headers.get("x-ratelimit-reset")
    if remaining == "0" and reset is not None:
        try:
            return max(0.0, float(reset) - time.time())
        except ValueError:
            pass
    return 60.0  # secondary limit with no hint: GitHub says to wait at least a minute


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def candidate_from_item(item: dict[str, Any], provenance: Provenance, mode: ServiceMode) -> Candidate | None:
    """Turn one search result into a Candidate, or None if it is not usable."""
    full_name = item.get("full_name")
    url = item.get("html_url")
    if not isinstance(full_name, str) or not FULL_NAME.match(full_name) or not isinstance(url, str):
        return None
    license_object = item.get("license")
    stars = item.get("stargazers_count")
    return Candidate(
        repo=full_name,
        url=url,
        description=item.get("description") if isinstance(item.get("description"), str) else None,
        language=item.get("language") if isinstance(item.get("language"), str) else None,
        topics=[t for t in item["topics"] if isinstance(t, str)] if isinstance(item.get("topics"), list) else None,
        license=license_object.get("spdx_id") if isinstance(license_object, dict) else None,
        archived=item.get("archived") if isinstance(item.get("archived"), bool) else None,
        last_push=_parse_time(item.get("pushed_at")),
        stars=stars if isinstance(stars, int) and stars >= 0 else None,
        homepage=item.get("homepage") if isinstance(item.get("homepage"), str) and item.get("homepage") else None,
        retrieved_at=provenance.retrieved_at,
        from_cache=provenance.from_cache,
        mode=mode,
    )


# Seconds between two search requests (60 / the hourly-minute allowance, plus a margin).
SEARCH_GAP_WITHOUT_TOKEN = 6.5
SEARCH_GAP_WITH_TOKEN = 2.2


class GitHubClient:
    def __init__(
        self,
        *,
        mode: ServiceMode,
        transport: httpx.AsyncBaseTransport | None = None,
        token: str | None = None,
        cache: ResponseCache | None = None,
        sleep: Sleep = asyncio.sleep,
        timeout: float = 15.0,
        user_agent: str = "Archway",
    ):
        self.mode = mode
        self._transport = transport
        self._token = token
        self._cache = cache or NoCache()
        self._sleep = sleep
        self._timeout = timeout
        self._user_agent = user_agent
        # LEARNING NOTE: pacing instead of recovering
        #   GitHub's search API allows 10 requests a minute without a token and
        #   30 with one. Agents search in parallel and blow through that in
        #   seconds, then every search fails for 40 to 60 s. Spacing the
        #   searches out costs a few seconds each; failing costs the search
        #   (and a model call to hear about it). Live mode only.
        self._search_gap = SEARCH_GAP_WITH_TOKEN if token else SEARCH_GAP_WITHOUT_TOKEN
        self._search_lock = asyncio.Lock()
        self._last_search = 0.0

    @property
    def authenticated(self) -> bool:
        return self._token is not None

    # --- The one request function ----------------------------------------------
    async def _get(self, path: str, *, params: dict | None = None, accept: str = "application/vnd.github+json"):
        """Returns (status_code, body_text, content_type, Provenance).

        Only 200 and 404 are answers. A rate limit raises GitHubRateLimited;
        any other failure raises GitHubError.
        """
        key = cache_key("GET", path, params, accept)
        cached = await self._cache.get(key)
        if cached is not None:
            return cached.status_code, cached.body, cached.content_type, Provenance(cached.retrieved_at, True, False)

        headers = {"Accept": accept, "X-GitHub-Api-Version": API_VERSION, "User-Agent": self._user_agent}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"

        if self.mode == "live" and path.startswith("/search/"):
            await self._pace_search()

        last_problem = "no attempt was made"
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                async with httpx.AsyncClient(
                    base_url=GITHUB_API, transport=self._transport, timeout=self._timeout, follow_redirects=False
                ) as client:
                    response = await client.get(path, params=params, headers=headers)
            except httpx.TimeoutException:
                last_problem = f"GitHub did not answer within {int(self._timeout)} seconds"
            except httpx.HTTPError as error:
                last_problem = f"could not reach GitHub ({type(error).__name__})"
            else:
                body = response.text
                wait = _wait_for_rate_limit(response, body)
                if wait is not None:
                    raise GitHubRateLimited(f"GitHub rate limit reached (retry in {int(wait)} s)", wait)
                if response.status_code in (200, 404):
                    retrieved_at = utc_now()
                    content_type = response.headers.get("content-type")
                    await self._cache.put(key, CachedResponse(response.status_code, content_type, body, retrieved_at))
                    return response.status_code, body, content_type, Provenance(retrieved_at, False, True)
                if response.status_code >= 500:
                    last_problem = f"GitHub answered HTTP {response.status_code}"
                else:
                    # 401 (bad token), 422 (bad query), plain 403 ... are not worth repeating.
                    raise GitHubError(f"GitHub answered HTTP {response.status_code}: {self._message_of(body)}")

            if attempt < MAX_ATTEMPTS:
                await self._sleep(0.5 * 2 ** (attempt - 1))  # 0.5 s, then 1 s

        raise GitHubError(f"{last_problem} (tried {MAX_ATTEMPTS} times)")

    async def rate_limits(self) -> dict[str, dict[str, int]] | None:
        """GitHub's own account of the limits, or None when it cannot be read.

        LEARNING NOTE: GET /rate_limit is free: asking does not use up any of
        the limits it reports. Returns {"core": {...}, "search": {...}}, each
        with limit, remaining and seconds_until_reset. Live mode only.
        """
        if self.mode != "live":
            return None
        headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": API_VERSION,
                   "User-Agent": self._user_agent}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        try:
            async with httpx.AsyncClient(base_url=GITHUB_API, transport=self._transport, timeout=self._timeout) as client:
                response = await client.get("/rate_limit", headers=headers)
            resources = response.json()["resources"] if response.status_code == 200 else None
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            return None
        if not isinstance(resources, dict):
            return None
        now = time.time()
        meters: dict[str, dict[str, int]] = {}
        for name in ("core", "search"):
            item = resources.get(name)
            if isinstance(item, dict) and all(isinstance(item.get(k), int) for k in ("limit", "remaining", "reset")):
                meters[name] = {"limit": item["limit"], "remaining": item["remaining"],
                                "seconds_until_reset": max(0, int(item["reset"] - now))}
        return meters or None

    async def _pace_search(self) -> None:
        """Leave at least `_search_gap` seconds between search requests (shared by all agents)."""
        async with self._search_lock:
            wait = self._last_search + self._search_gap - time.monotonic()
            if wait > 0:
                await self._sleep(wait)
            self._last_search = time.monotonic()

    @staticmethod
    def _message_of(body: str) -> str:
        try:
            return scrub(str(json.loads(body).get("message", ""))[:200])
        except (ValueError, AttributeError):
            return scrub(body[:200])

    # --- The three questions ----------------------------------------------------
    async def search_repositories(self, query: str, *, per_page: int = 10) -> SearchOutcome:
        status, body, _, provenance = await self._get(
            "/search/repositories", params={"q": query, "per_page": per_page}
        )
        if status != 200:
            raise GitHubError(f"search answered HTTP {status}")
        try:
            data = json.loads(body)
            items = data["items"]
        except (ValueError, KeyError, TypeError) as error:
            raise GitHubError("GitHub's search reply was not the expected JSON") from error
        candidates = [
            candidate for item in items if isinstance(item, dict)
            if (candidate := candidate_from_item(item, provenance, self.mode)) is not None
        ]
        return SearchOutcome(candidates, bool(data.get("incomplete_results")), provenance)

    async def get_repository(self, full_name: str) -> Candidate | None:
        """One repository's details by name (GET /repos/{owner}/{name}), or None if it does not exist.

        The answer is the same repository object a search returns, so it is
        read with the same function.
        """
        self._check_name(full_name)
        status, body, _, provenance = await self._get(f"/repos/{full_name}")
        if status == 404:
            return None
        try:
            item = json.loads(body)
        except ValueError as error:
            raise GitHubError("GitHub's repository reply was not the expected JSON") from error
        return candidate_from_item(item, provenance, self.mode) if isinstance(item, dict) else None

    async def get_readme(self, full_name: str) -> ReadmeOutcome:
        self._check_name(full_name)
        status, body, _, provenance = await self._get(
            f"/repos/{full_name}/readme", accept="application/vnd.github.raw+json"
        )
        if status == 404:
            return ReadmeOutcome(None, False, False, None, provenance)
        truncated = len(body) > MAX_README_CHARS
        return ReadmeOutcome(body[:MAX_README_CHARS], True, truncated, f"https://github.com/{full_name}#readme", provenance)

    async def get_license(self, full_name: str) -> LicenseOutcome:
        self._check_name(full_name)
        status, body, _, provenance = await self._get(f"/repos/{full_name}/license")
        if status == 404:
            return LicenseOutcome(None, None, False, provenance)
        try:
            license_object = json.loads(body).get("license")
        except (ValueError, AttributeError) as error:
            raise GitHubError("GitHub's license reply was not the expected JSON") from error
        if not isinstance(license_object, dict):
            return LicenseOutcome(None, None, False, provenance)
        return LicenseOutcome(license_object.get("spdx_id"), license_object.get("name"), True, provenance)

    @staticmethod
    def _check_name(full_name: str) -> None:
        # The name goes into a URL path, so it must look like owner/name and nothing else.
        if not FULL_NAME.match(full_name):
            raise GitHubError(f"{full_name!r} is not a repository name")
