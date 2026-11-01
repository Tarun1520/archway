"""
Lesson 21: Safe URL checks (blocking requests to private networks)
==================================================================

What you learn here
    If a program fetches a URL a USER gave it, the user can point it at
    addresses that only the server can reach (your own machine, your home
    router, cloud metadata). That attack is called SSRF (server-side request
    forgery). The defence is to check where the URL REALLY goes:
      1. scheme must be https
      2. the hostname must resolve to PUBLIC addresses only
      3. check the RESOLVED IP, not just the text of the hostname
      4. check again on every redirect hop

    The code uses Python's standard `ipaddress` module and an injectable
    "resolver" function, so this lesson makes NO network requests.

How to run (from the project root)
    backend/.venv/bin/python backend/learning/21_safe_url_checks.py

Where Archway uses this
    Phase 3 (research) for user-supplied URLs and links found in READMEs.
    Checkpoint 3: "Private-network and localhost URLs are rejected, including
    via redirect and via a hostname that resolves to a private address."

NOTE: this is a teaching version. Before it protects a real fetcher it also
needs size, time and content-type limits, and a redirect-following loop that
calls `check_url` for every hop (PART 2 shows that idea).
"""

import ipaddress
from collections.abc import Callable
from urllib.parse import urlparse

# A "resolver" turns a hostname into a list of IP address strings.
Resolver = Callable[[str], list[str]]


class UnsafeUrl(Exception):
    """Raised when a URL must not be fetched. The message says why."""


def check_url(url: str, resolve: Resolver) -> None:
    """Return quietly if the URL is allowed, otherwise raise UnsafeUrl."""
    parts = urlparse(url)

    if parts.scheme != "https":
        raise UnsafeUrl(f"scheme {parts.scheme!r} is not allowed (https only)")
    if not parts.hostname:
        raise UnsafeUrl("no hostname")
    if parts.username or parts.password:
        raise UnsafeUrl("credentials inside the URL are not allowed")

    # LEARNING NOTE: why resolve first?
    #   "internal.example.com" looks harmless as text but may point at
    #   10.0.0.5. Only the resolved address tells the truth.
    addresses = resolve(parts.hostname)
    if not addresses:
        raise UnsafeUrl("hostname did not resolve")

    for text in addresses:
        address = ipaddress.ip_address(text)
        # IPv6 can wrap an IPv4 address ("::ffff:127.0.0.1"). Unwrap it first.
        if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
            address = address.ipv4_mapped
        # `is_global` is True only for addresses that are routable on the
        # public internet. Private, loopback, link-local, reserved, and
        # documentation ranges are all False.
        if not address.is_global:
            raise UnsafeUrl(f"{parts.hostname} resolves to non-public address {address}")


# -----------------------------------------------------------------------------
# Offline demo support: a fake DNS table
# -----------------------------------------------------------------------------
FAKE_DNS = {
    "github.com": ["8.8.4.4"],  # stands in for a public address
    "docs.example.org": ["8.8.8.8"],
    "intranet.example.org": ["10.0.0.5"],  # a PUBLIC-looking name, private target
    "localhost": ["127.0.0.1", "::1"],
    "metadata.example.org": ["169.254.169.254"],  # cloud metadata address
    "sneaky.example.org": ["::ffff:127.0.0.1"],  # IPv4 wrapped in IPv6
    "mixed.example.org": ["8.8.8.8", "192.168.1.10"],  # one good, one bad
}


def fake_resolver(hostname: str) -> list[str]:
    return FAKE_DNS.get(hostname, [])


def follow_redirects(start: str, redirects: dict[str, str], resolve: Resolver, max_hops: int = 5) -> str:
    """PART 2: re-check EVERY hop. A safe first URL can redirect somewhere unsafe."""
    url = start
    for _ in range(max_hops):
        check_url(url, resolve)  # the check runs on every hop
        if url not in redirects:
            return url  # no further redirect: this is the final URL
        url = redirects[url]
    raise UnsafeUrl("too many redirects")


if __name__ == "__main__":
    print("PART 1: individual URLs")
    samples = [
        "https://github.com/example/notes-md",
        "http://github.com/example/notes-md",
        "https://localhost/admin",
        "https://127.0.0.1/",
        "https://intranet.example.org/secret",
        "https://metadata.example.org/latest",
        "https://sneaky.example.org/",
        "https://mixed.example.org/",
        "https://user:pass@github.com/",
        "https://unknown-host.example/",
    ]
    for url in samples:
        try:
            # For literal IPs, the "resolver" just echoes the address back.
            resolver = (lambda h: [h]) if url.split("/")[2].replace(".", "").isdigit() else fake_resolver
            check_url(url, resolver)
            print(f"  ALLOWED  {url}")
        except UnsafeUrl as error:
            print(f"  REFUSED  {url}\n           why: {error}")

    print("\nPART 2: a redirect chain whose second hop is unsafe")
    redirects = {"https://github.com/old-name": "https://intranet.example.org/secret"}
    try:
        follow_redirects("https://github.com/old-name", redirects, fake_resolver)
    except UnsafeUrl as error:
        print("  REFUSED on the redirect hop:", error)
