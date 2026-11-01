"""
Lesson 25: Connect to the address you checked (closing a DNS-rebinding gap)
===========================================================================

What you learn here
    Lesson 21 checked a URL's resolved address. But if you then hand the URL
    to an HTTP library, it looks the name up AGAIN. A hostile DNS server can
    answer "public address" for your check and "10.0.0.5" for the real
    connection (DNS rebinding). The check was true, and useless.

    The fix is to connect to the very IP you checked, and tell TLS the real
    hostname separately so the certificate is still verified for that name:

        URL:        https://<the checked IP>/path
        Host:       the real hostname      (what the site sees)
        sni_hostname extension: the real hostname (what TLS verifies)

    This lesson runs offline: a fake resolver and a fake network show
    exactly what would be sent. (The same code was also run against a real
    site while building Phase 3: with the right name the certificate was
    accepted, with no name the handshake failed.)

How to run (from the project root)
    backend/.venv/bin/python backend/learning/25_pinned_ip_fetch.py

Where Archway uses this
    backend/app/research/safe_fetch.py (Phase 3), for user-supplied and
    repository-linked documentation addresses.
"""

import asyncio

import httpx

# Make `import app...` work when this script is run directly.
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.integrations.safe_fetch import FetchRefused, SafeFetcher  # noqa: E402

# A "DNS" that behaves like a rebinding attacker: the SECOND answer is private.
answers_given: list[str] = []


async def rebinding_resolver(hostname: str) -> list[str]:
    answers_given.append(hostname)
    return ["8.8.8.8"] if len(answers_given) == 1 else ["10.0.0.5"]


def network(request: httpx.Request) -> httpx.Response:
    print(f"   request went to: {request.url}   Host header: {request.headers['host']}")
    return httpx.Response(200, text="hello", headers={"content-type": "text/plain"})


async def main() -> None:
    fetcher = SafeFetcher(resolver=rebinding_resolver, transport=httpx.MockTransport(network))

    print("1. The name is looked up ONCE, checked, and that exact address is used:")
    page = await fetcher.fetch("https://rebinding.example.org/page")
    print("   lookups made:", len(answers_given), "| page text:", page.text)
    print("   (A second lookup, which would have said 10.0.0.5, never happens.)")

    print("\n2. A fresh fetch sees the private answer and is refused before any request:")
    try:
        await fetcher.fetch("https://rebinding.example.org/page")
    except FetchRefused as error:
        print("   ", error.message)


if __name__ == "__main__":
    asyncio.run(main())
