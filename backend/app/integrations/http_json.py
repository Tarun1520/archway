"""
A small, careful HTTP helper for public JSON APIs (PyPI, the npm registry).

What it does, once, so each client does not repeat it
    - sends a GET with a time limit
    - retries a timeout, a connection error or a 5xx answer up to 3 times,
      with short waits (the wait function is injectable, so tests never sleep)
    - reports a 429 as RegistryRateLimited, never as "not found"
    - treats 200 and 404 as answers; anything else is an error
    - uses the response cache (original retrieval dates kept)

How it plugs in
    app/integrations/pypi_client.py and npm_client.py use it.
    (The GitHub client has its own version, because GitHub's rate limits
    have their own headers and rules.)
"""

import asyncio
from collections.abc import Awaitable, Callable

import httpx

from app.integrations.cache import CachedResponse, NoCache, ResponseCache, cache_key
from app.integrations.github_client import Provenance
from app.models.common import utc_now

MAX_ATTEMPTS = 3
Sleep = Callable[[float], Awaitable[None]]


class RegistryError(Exception):
    """A request failed. The message is safe to show."""


class RegistryRateLimited(RegistryError):
    def __init__(self, message: str, wait_seconds: float):
        super().__init__(message)
        self.wait_seconds = wait_seconds


class JsonHttp:
    def __init__(
        self,
        *,
        base_url: str,
        service: str,
        transport: httpx.AsyncBaseTransport | None = None,
        cache: ResponseCache | None = None,
        sleep: Sleep = asyncio.sleep,
        timeout: float = 15.0,
        user_agent: str = "Archway",
    ):
        self._base_url = base_url
        self._service = service
        self._transport = transport
        self._cache = cache or NoCache()
        self._sleep = sleep
        self._timeout = timeout
        self._user_agent = user_agent

    async def get(self, path: str, params: dict | None = None) -> tuple[int, str, Provenance]:
        key = cache_key("GET", self._base_url + path, params, "application/json")
        cached = await self._cache.get(key)
        if cached is not None:
            return cached.status_code, cached.body, Provenance(cached.retrieved_at, True, False)

        problem = "no attempt was made"
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                async with httpx.AsyncClient(
                    base_url=self._base_url, transport=self._transport, timeout=self._timeout, follow_redirects=True
                ) as client:
                    response = await client.get(
                        path, params=params, headers={"Accept": "application/json", "User-Agent": self._user_agent}
                    )
            except httpx.TimeoutException:
                problem = f"{self._service} did not answer within {int(self._timeout)} seconds"
            except httpx.HTTPError as error:
                problem = f"could not reach {self._service} ({type(error).__name__})"
            else:
                if response.status_code == 429:
                    try:
                        wait = float(response.headers.get("retry-after", "60"))
                    except ValueError:
                        wait = 60.0
                    raise RegistryRateLimited(f"{self._service} rate limit reached", wait)
                if response.status_code in (200, 404):
                    now = utc_now()
                    await self._cache.put(key, CachedResponse(response.status_code, response.headers.get("content-type"),
                                                              response.text, now))
                    return response.status_code, response.text, Provenance(now, False, True)
                if response.status_code < 500:
                    raise RegistryError(f"{self._service} answered HTTP {response.status_code}")
                problem = f"{self._service} answered HTTP {response.status_code}"
            if attempt < MAX_ATTEMPTS:
                await self._sleep(0.5 * 2 ** (attempt - 1))
        raise RegistryError(f"{problem} (tried {MAX_ATTEMPTS} times)")
