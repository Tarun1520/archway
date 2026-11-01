"""
Web search through the Brave Search API (optional: needs BRAVE_API_KEY).

What this file does
    Sends one keyword query to Brave's web search and returns the top results
    (title, address, short description). Switched on only when a key is set;
    without one the tool is simply not offered to the agents.

Same rule as discussion search
    A result is a LEAD. Any project or package it names must still be verified
    through GitHub, PyPI or npm, and its text is untrusted data.

Documented behaviour used (api.search.brave.com): GET /res/v1/web/search with
`q` and `count`, header `X-Subscription-Token`; results are in
`web.results[]` with `title`, `url`, `description`.
"""

import html
import re
from dataclasses import dataclass

import httpx

BRAVE_URL = "https://api.search.brave.com/res/v1/web/search"
TIMEOUT_SECONDS = 12.0
_TAGS = re.compile(r"<[^>]+>")


class WebSearchError(Exception):
    pass


@dataclass(frozen=True)
class WebHit:
    title: str
    url: str
    description: str


class WebSearchClient:
    mode = "live"

    def __init__(self, *, api_key: str, transport: httpx.AsyncBaseTransport | None = None):
        self._api_key = api_key
        self._transport = transport

    async def search(self, query: str, count: int = 6) -> list[WebHit]:
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS, transport=self._transport) as client:
                response = await client.get(
                    BRAVE_URL, params={"q": query, "count": count},
                    # The key travels in a header; it is never logged or put in an error message.
                    headers={"X-Subscription-Token": self._api_key, "Accept": "application/json"},
                )
        except httpx.HTTPError as error:
            raise WebSearchError(f"web search could not be reached ({type(error).__name__})") from error
        if response.status_code == 429:
            raise WebSearchError("web search rate limit reached")
        if response.status_code != 200:
            raise WebSearchError(f"web search answered HTTP {response.status_code}")
        try:
            results = response.json()["web"]["results"]
        except (KeyError, TypeError, ValueError) as error:
            raise WebSearchError("web search returned a reply that was not the expected JSON") from error
        clean = lambda text, n: " ".join(html.unescape(_TAGS.sub("", text or "")).split())[:n]  # noqa: E731
        return [WebHit(clean(r.get("title"), 120), r.get("url", ""), clean(r.get("description"), 200))
                for r in results if r.get("url")][:count]
