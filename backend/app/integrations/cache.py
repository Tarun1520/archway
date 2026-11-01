"""
A small cache for GitHub answers.

What this file does
    Remembers what GitHub answered, so asking the same thing again does not
    spend a request, and so the answer carries its ORIGINAL retrieval date.

The rule it protects (IMPLEMENTATION_GUIDE.md section 6.1)
    "Cached data keeps and displays its original retrieval date." A cached
    answer is never shown as if it were fetched just now.

Three versions, one interface
    MemoryCache   a dictionary. Used in tests.
    SqliteCache   the real one: a table in archway.db, with an expiry.
    NoCache       does nothing. Used in fixture mode, so recorded demo data
                  can never be saved and later mistaken for live data.

How it plugs in
    app/research/github_client.py asks the cache before every request.
"""

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Protocol

from app.db.connection import open_connection
from app.models.common import utc_now


@dataclass(frozen=True)
class CachedResponse:
    status_code: int
    content_type: str | None
    body: str
    retrieved_at: datetime  # when GitHub first gave this answer


class ResponseCache(Protocol):
    async def get(self, key: str) -> CachedResponse | None: ...

    async def put(self, key: str, response: CachedResponse) -> None: ...


def cache_key(method: str, url: str, params: dict | None, accept: str) -> str:
    """A fixed-length name for one request, the same every time for the same request."""
    parts = [method, url, repr(sorted((params or {}).items())), accept]
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()


class NoCache:
    async def get(self, key: str) -> CachedResponse | None:
        return None

    async def put(self, key: str, response: CachedResponse) -> None:
        return None


class MemoryCache:
    def __init__(self, ttl: timedelta = timedelta(hours=24)):
        self._items: dict[str, CachedResponse] = {}
        self._ttl = ttl

    async def get(self, key: str) -> CachedResponse | None:
        item = self._items.get(key)
        if item is None or utc_now() - item.retrieved_at > self._ttl:
            return None
        return item

    async def put(self, key: str, response: CachedResponse) -> None:
        self._items[key] = response


class SqliteCache:
    def __init__(self, database_path: Path, ttl: timedelta = timedelta(hours=24)):
        self._path = database_path
        self._ttl = ttl

    async def get(self, key: str) -> CachedResponse | None:
        async with open_connection(self._path) as db:
            cursor = await db.execute("SELECT * FROM github_cache WHERE cache_key = ?", (key,))
            row = await cursor.fetchone()
        if row is None:
            return None
        retrieved_at = datetime.fromisoformat(row["retrieved_at"])
        if utc_now() - retrieved_at > self._ttl:
            return None  # too old: ask GitHub again (the new answer gets a new date)
        return CachedResponse(row["status_code"], row["content_type"], row["body"], retrieved_at)

    async def put(self, key: str, response: CachedResponse) -> None:
        async with open_connection(self._path) as db:
            await db.execute(
                """
                INSERT INTO github_cache (cache_key, status_code, content_type, body, retrieved_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT (cache_key) DO UPDATE SET
                    status_code = excluded.status_code, content_type = excluded.content_type,
                    body = excluded.body, retrieved_at = excluded.retrieved_at
                """,
                (key, response.status_code, response.content_type, response.body, response.retrieved_at.isoformat()),
            )
            await db.commit()
