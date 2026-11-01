"""
Lesson 23: Content hashes, excerpts, and a cache that keeps the ORIGINAL date
=============================================================================

What you learn here
    1. HASH: a short fingerprint of some content (SHA-256). Same content gives
       the same fingerprint; any change gives a completely different one. It
       lets you notice "this README changed since we looked".
    2. EXCERPT WITH LOCATION: store a short quote AND where it came from,
       instead of copying whole documents.
    3. CACHE THAT KEEPS ITS DATE: when you serve a saved copy, show when it
       was ORIGINALLY retrieved, never "just now".

How to run (from the project root)
    backend/.venv/bin/python backend/learning/23_evidence_hash_and_cache.py

Where Archway uses this
    Phase 3, `normalize_evidence` and the GitHub client cache. Section 6.2:
    "content hash", "short relevant excerpt with location", and "Cached data
    keeps and displays its original retrieval date".
"""

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx


@dataclass(frozen=True)
class EvidenceItem:
    url: str
    retrieved_at: datetime  # when it was FIRST fetched
    content_hash: str
    excerpt: str
    excerpt_location: str  # e.g. "characters 40-95"
    from_cache: bool


def sha256_of(text: str) -> str:
    # Hashes work on bytes, so encode the text first.
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def make_excerpt(text: str, start: int, length: int = 60) -> tuple[str, str]:
    """A short quote plus its location. Keep excerpts short on purpose."""
    end = min(start + length, len(text))
    return text[start:end], f"characters {start}-{end}"


class EvidenceFetcher:
    def __init__(self, client: httpx.Client):
        self.client = client
        self._cache: dict[str, EvidenceItem] = {}

    def get(self, url: str) -> EvidenceItem:
        if url in self._cache:
            saved = self._cache[url]
            # Same object, same ORIGINAL retrieved_at; only the flag differs.
            return EvidenceItem(
                saved.url, saved.retrieved_at, saved.content_hash,
                saved.excerpt, saved.excerpt_location, from_cache=True,
            )
        response = self.client.get(url)
        response.raise_for_status()
        text = response.text
        excerpt, location = make_excerpt(text, start=0)
        item = EvidenceItem(
            url, datetime.now(timezone.utc), sha256_of(text), excerpt, location, from_cache=False
        )
        self._cache[url] = item
        return item


if __name__ == "__main__":
    # FIXTURE: a fake server that counts how often it is asked.
    asked = {"times": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        asked["times"] += 1
        return httpx.Response(200, text="# notes-md\nA small markdown notes app with offline search.")

    fetcher = EvidenceFetcher(httpx.Client(transport=httpx.MockTransport(handler)))

    first = fetcher.get("https://example.test/readme")
    second = fetcher.get("https://example.test/readme")

    print("first fetch :", first.retrieved_at.isoformat(), "| from_cache:", first.from_cache)
    print("second fetch:", second.retrieved_at.isoformat(), "| from_cache:", second.from_cache)
    print("same original date kept:", first.retrieved_at == second.retrieved_at)
    print("server was asked", asked["times"], "time(s)")
    print("\nhash   :", first.content_hash[:24] + "...")
    print("excerpt:", repr(first.excerpt), "|", first.excerpt_location)

    print("\nOne changed character gives a totally different hash:")
    print("  ", sha256_of("hello")[:24] + "...")
    print("  ", sha256_of("hellp")[:24] + "...")
