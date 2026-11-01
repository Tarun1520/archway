"""
Discussion search: what practitioners actually recommend, from public forums.

What this file does
    Searches two public, keyless sources for threads about a technical need:
      Hacker News   (hn.algolia.com)       "Show HN" launches and discussions
      Stack Overflow (api.stackexchange.com) questions with votes and answers
    and returns a short, merged list of hits.

Why it exists (found live)
    Scouts only knew what the model remembered plus what GitHub, PyPI and npm
    search returned. Practitioners' threads name the tools people really use
    (a Hacker News search for "open source voice agent framework" returns the
    Pipecat-based projects that the scouts missed).

The rule that keeps it safe
    A thread is a LEAD, never a source of facts. A tool name found here must
    still be verified through GitHub, PyPI or npm before it can be proposed,
    and a post's text is untrusted data, never instructions.

Reddit
    Deliberately left out: anonymous access is refused (HTTP 403), and its API
    needs a registered app and has usage terms. The two sources above carry
    most of the signal without any key.

Fixture mode returns a small fixed list, so tests and demos need no network.
"""

import asyncio
import html
import re
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx

HN_URL = "https://hn.algolia.com/api/v1/search"
SO_URL = "https://api.stackexchange.com/2.3/search/advanced"
TIMEOUT_SECONDS = 12.0
_TAGS = re.compile(r"<[^>]+>")


@dataclass(frozen=True)
class DiscussionHit:
    source: str  # "hacker_news" | "stack_overflow"
    title: str
    url: str
    points: int  # HN points, or Stack Overflow score
    replies: int  # HN comments, or Stack Overflow answers
    created: str | None  # ISO date


def _clean(text: str, limit: int = 140) -> str:
    return " ".join(html.unescape(_TAGS.sub("", text or "")).split())[:limit]


def _iso(epoch: int | float | None) -> str | None:
    if not isinstance(epoch, (int, float)):
        return None
    return datetime.fromtimestamp(epoch, tz=timezone.utc).date().isoformat()


class DiscussionClient:
    def __init__(self, *, mode: str, transport: httpx.AsyncBaseTransport | None = None):
        self.mode = mode
        self._transport = transport

    async def search(self, query: str, per_source: int = 4) -> tuple[list[DiscussionHit], list[str]]:
        """Returns (hits, problems). A source that fails is reported, not fatal."""
        if self.mode != "live":
            return _fixture_hits(query), []
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS, transport=self._transport,
                                     headers={"User-Agent": "Archway/0.1 (research tool)"}) as client:
            results = await asyncio.gather(
                self._hacker_news(client, query, per_source), self._stack_overflow(client, query, per_source),
                return_exceptions=True,
            )
        hits: list[DiscussionHit] = []
        problems: list[str] = []
        for name, result in zip(("Hacker News", "Stack Overflow"), results):
            if isinstance(result, Exception):
                problems.append(f"{name} could not be searched ({type(result).__name__})")
            else:
                hits.extend(result)
        return hits, problems

    async def _hacker_news(self, client: httpx.AsyncClient, query: str, limit: int) -> list[DiscussionHit]:
        response = await client.get(HN_URL, params={"query": query, "tags": "story", "hitsPerPage": limit * 2})
        response.raise_for_status()
        hits = []
        for item in response.json().get("hits", []):
            title, points = _clean(item.get("title") or item.get("story_title") or ""), item.get("points") or 0
            if not title or points < 2:
                continue
            thread = f"https://news.ycombinator.com/item?id={item.get('objectID')}"
            hits.append(DiscussionHit("hacker_news", title, item.get("url") or thread, int(points),
                                      int(item.get("num_comments") or 0), _iso(item.get("created_at_i"))))
        return hits[:limit]

    async def _stack_overflow(self, client: httpx.AsyncClient, query: str, limit: int) -> list[DiscussionHit]:
        response = await client.get(SO_URL, params={
            "order": "desc", "sort": "relevance", "q": query, "site": "stackoverflow", "pagesize": limit,
        })
        response.raise_for_status()
        return [
            DiscussionHit("stack_overflow", _clean(item.get("title", "")), item.get("link", ""), int(item.get("score") or 0),
                          int(item.get("answer_count") or 0), _iso(item.get("creation_date")))
            for item in response.json().get("items", []) if item.get("title") and item.get("link")
        ]


def _fixture_hits(query: str) -> list[DiscussionHit]:
    return [
        DiscussionHit("hacker_news", f"FIXTURE: Show HN, an open-source tool for {query[:50]}",
                      "https://news.ycombinator.com/item?id=0", 10, 3, "2026-01-01"),
        DiscussionHit("stack_overflow", f"FIXTURE: How do I do {query[:50]}?",
                      "https://stackoverflow.com/questions/0", 5, 2, "2026-01-01"),
    ]
