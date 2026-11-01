"""
SafeFetcher: fetching a web page that a user, or a README, pointed at.

Why this needs care
    A program that fetches an address someone else chose can be steered at
    places only the server can reach: your own machine, your home router,
    cloud metadata (an attack called SSRF). The rules below are the
    IMPLEMENTATION_GUIDE.md section 6.1 rules, one by one:

      1. https only                                     check_url
      2. no credentials in the address                  check_url
      3. only the normal https port                     check_url
      4. the name must resolve to PUBLIC addresses      check_url
         (the RESOLVED address is checked, not the name)
      5. every redirect hop is checked again            fetch
      6. a time limit                                   timeout
      7. a size limit                                   max_bytes
      8. only text-like content types                   ALLOWED_TYPES

The detail that makes rule 4 real: connect to the address you checked
    Checking an address and then letting the HTTP library look the name up
    AGAIN leaves a gap: a hostile DNS server can answer "public" the first
    time and "private" the second (DNS rebinding). So after the check we
    connect to the very IP we checked, and tell TLS the real hostname with
    `sni_hostname`, so the certificate is still verified for that name.
    Verified against a live site while building this (a request to the
    pinned address with the right name worked; with no name it failed).

    A new HTTP client is made for every hop, so a connection verified for
    one hostname is never reused for another.

How it plugs in
    app/research/factory.py builds one (live, or fixture with recorded pages).
    app/graph/nodes/fetch_docs.py calls `fetch`.

Learn more: LEARNING_GUIDE.md topic 37 and backend/learning/21_safe_url_checks.py.
"""

import asyncio
import ipaddress
import socket
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from urllib.parse import urljoin, urlparse

import httpx

from app.models.common import utc_now

Resolver = Callable[[str], Awaitable[list[str]]]

ALLOWED_TYPES = ("text/html", "text/plain", "text/markdown", "application/xhtml+xml", "application/json")
BLOCKED_SUFFIXES = (".localhost", ".local", ".internal", ".home.arpa", ".lan")
MAX_BYTES = 300_000
MAX_REDIRECTS = 3
TIMEOUT_SECONDS = 10.0
USER_AGENT = "Archway"


class FetchRefused(Exception):
    """The page was not fetched. `message` says why and is safe to show."""

    def __init__(self, kind: Literal["unsafe", "unsupported", "failed"], message: str):
        super().__init__(message)
        self.kind = kind
        self.message = message


@dataclass(frozen=True)
class SafeTarget:
    url: str
    hostname: str
    address: str  # the IP address that passed the checks, and the one we connect to


@dataclass(frozen=True)
class FetchedPage:
    url: str  # the final address, after any redirects
    content_type: str
    text: str
    truncated: bool
    retrieved_at: datetime
    redirects: tuple[str, ...]


async def system_resolver(hostname: str) -> list[str]:
    """Ask the operating system's name service. Failure means "no addresses"."""
    try:
        infos = await asyncio.get_running_loop().getaddrinfo(hostname, 443, type=socket.SOCK_STREAM)
    except OSError:
        return []
    return sorted({info[4][0] for info in infos})


async def check_url(url: str, resolve: Resolver) -> SafeTarget:
    """Return the safe target for a URL, or raise FetchRefused("unsafe", why)."""
    try:
        parts = urlparse(url)
        port = parts.port
    except ValueError:
        raise FetchRefused("unsafe", "refused: the address is not valid") from None

    if parts.scheme != "https":
        raise FetchRefused("unsafe", f"refused: only https addresses are allowed (this one is {parts.scheme or 'not a web address'})")
    hostname = (parts.hostname or "").rstrip(".").lower()
    if not hostname:
        raise FetchRefused("unsafe", "refused: the address has no host name")
    if parts.username or parts.password:
        raise FetchRefused("unsafe", "refused: addresses with a user name or password are not allowed")
    if port not in (None, 443):
        raise FetchRefused("unsafe", f"refused: port {port} is not allowed (only the normal https port)")
    if hostname == "localhost" or hostname.endswith(BLOCKED_SUFFIXES):
        raise FetchRefused("unsafe", f"refused: {hostname} is a local name")

    # A literal address needs no lookup. Anything else is resolved.
    try:
        ipaddress.ip_address(hostname)
        addresses = [hostname]
    except ValueError:
        addresses = await resolve(hostname)
    if not addresses:
        raise FetchRefused("unsafe", f"refused: {hostname} did not resolve to an address")

    parsed: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    for text in addresses:
        address = ipaddress.ip_address(text)
        # IPv6 can wrap an IPv4 address ("::ffff:127.0.0.1"). Unwrap it first.
        if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
            address = address.ipv4_mapped
        # `is_global` is True only for addresses routable on the public
        # internet. Private, loopback, link-local, reserved and documentation
        # ranges are all False. ONE bad address refuses the whole name.
        if not address.is_global:
            raise FetchRefused("unsafe", f"refused: {hostname} resolves to a non-public address ({address})")
        parsed.append(address)

    chosen = next((a for a in parsed if a.version == 4), parsed[0])
    return SafeTarget(url=url, hostname=hostname, address=str(chosen))


def _pinned_url(target: SafeTarget) -> str:
    """The same address, but with the checked IP in place of the name."""
    parts = urlparse(target.url)
    host = f"[{target.address}]" if ":" in target.address else target.address
    path = parts.path or "/"
    return f"https://{host}{path}" + (f"?{parts.query}" if parts.query else "")


def _charset_of(content_type: str) -> str:
    for piece in content_type.split(";")[1:]:
        name, _, value = piece.strip().partition("=")
        if name.lower() == "charset" and value:
            return value.strip("\"'")
    return "utf-8"


class SafeFetcher:
    def __init__(
        self,
        *,
        resolver: Resolver = system_resolver,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: float = TIMEOUT_SECONDS,
        max_bytes: int = MAX_BYTES,
        max_redirects: int = MAX_REDIRECTS,
    ):
        self._resolve = resolver
        self._transport = transport
        self._timeout = timeout
        self._max_bytes = max_bytes
        self._max_redirects = max_redirects

    async def fetch(self, url: str) -> FetchedPage:
        current = url
        redirects: list[str] = []

        for _ in range(self._max_redirects + 1):
            target = await check_url(current, self._resolve)  # every hop, including the first
            headers = {
                "Host": target.hostname,
                "User-Agent": USER_AGENT,
                "Accept": "text/html,text/plain,text/markdown,application/json;q=0.9,*/*;q=0.1",
            }
            try:
                async with httpx.AsyncClient(
                    transport=self._transport, timeout=self._timeout, follow_redirects=False
                ) as client:
                    async with client.stream(
                        "GET", _pinned_url(target), headers=headers, extensions={"sni_hostname": target.hostname}
                    ) as response:
                        if response.status_code in (301, 302, 303, 307, 308):
                            location = response.headers.get("location")
                            if not location:
                                raise FetchRefused("failed", "the server redirected without saying where")
                            current = urljoin(current, location)
                            redirects.append(current)
                            continue  # the next loop turn checks the new address
                        if response.status_code != 200:
                            raise FetchRefused("failed", f"the server answered HTTP {response.status_code}")

                        content_type = response.headers.get("content-type", "")
                        if not content_type.lower().startswith(ALLOWED_TYPES):
                            raise FetchRefused(
                                "unsupported", f"not read: the content type is {content_type or 'unknown'}, not text"
                            )

                        received = bytearray()
                        truncated = False
                        async for chunk in response.aiter_bytes():
                            received.extend(chunk)
                            if len(received) > self._max_bytes:
                                truncated = True
                                del received[self._max_bytes:]
                                break
            except FetchRefused:
                raise
            except httpx.TimeoutException:
                raise FetchRefused("failed", f"timed out after {int(self._timeout)} seconds") from None
            except httpx.HTTPError as error:
                raise FetchRefused("failed", f"could not connect ({type(error).__name__})") from None

            text = bytes(received).decode(_charset_of(content_type), errors="replace")
            return FetchedPage(current, content_type, text, truncated, utc_now(), tuple(redirects))

        raise FetchRefused("failed", f"too many redirects (more than {self._max_redirects})")
