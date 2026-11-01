"""
Tests for the safe page fetcher: Checkpoint 3's "private-network and
localhost URLs are rejected, including via redirect and via a hostname that
resolves to a private address".

A fake resolver stands in for DNS, and a fake transport for the network, so
every case is exact and nothing leaves the machine.
"""

import httpx
import pytest

from app.integrations.safe_fetch import FetchRefused, SafeFetcher, check_url

DNS = {
    "docs.example.org": ["8.8.8.8"],
    "other.example.org": ["8.8.4.4"],
    "intranet.example.org": ["10.0.0.5"],      # a public-looking NAME, private target
    "metadata.example.org": ["169.254.169.254"],
    "loopback.example.org": ["127.0.0.1"],
    "wrapped.example.org": ["::ffff:127.0.0.1"],
    "mixed.example.org": ["8.8.8.8", "192.168.1.10"],
    "v6.example.org": ["2606:4700:4700::1111"],
}


async def resolver(host):
    return DNS.get(host, [])


def fetcher_for(handler, **kwargs):
    return SafeFetcher(resolver=resolver, transport=httpx.MockTransport(handler), **kwargs)


def ok(body="<html><body><p>Hello docs</p></body></html>", content_type="text/html"):
    return lambda request: httpx.Response(200, text=body, headers={"content-type": content_type})


# --- Which addresses are refused -------------------------------------------------
@pytest.mark.parametrize("url, reason", [
    ("http://docs.example.org/", "only https"),
    ("ftp://docs.example.org/", "only https"),
    ("https://user:pw@docs.example.org/", "user name or password"),
    ("https://docs.example.org:8443/", "port 8443"),
    ("https://localhost/admin", "local name"),
    ("https://thing.localhost/", "local name"),
    ("https://printer.local/", "local name"),
    ("https://127.0.0.1/", "non-public"),
    ("https://[::1]/", "non-public"),
    ("https://10.1.2.3/", "non-public"),
    ("https://192.168.0.1/", "non-public"),
    ("https://169.254.169.254/latest/meta-data", "non-public"),
    ("https://intranet.example.org/", "non-public"),     # resolves privately
    ("https://metadata.example.org/", "non-public"),
    ("https://loopback.example.org/", "non-public"),
    ("https://wrapped.example.org/", "non-public"),     # IPv4 hidden inside IPv6
    ("https://mixed.example.org/", "non-public"),       # one bad address refuses the name
    ("https://unknown.example.org/", "did not resolve"),
    ("https:///path", "no host"),
])
async def test_unsafe_addresses_are_refused(url, reason):
    with pytest.raises(FetchRefused) as caught:
        await check_url(url, resolver)
    assert caught.value.kind == "unsafe" and reason in caught.value.message


async def test_public_addresses_are_allowed_and_ipv4_is_preferred():
    target = await check_url("https://docs.example.org/guide", resolver)
    assert (target.hostname, target.address) == ("docs.example.org", "8.8.8.8")
    assert (await check_url("https://v6.example.org/", resolver)).address == "2606:4700:4700::1111"


# --- What is sent ------------------------------------------------------------------
async def test_the_request_goes_to_the_checked_ip_with_the_real_name_in_host():
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        seen["host"] = request.headers["host"]
        return httpx.Response(200, text="hello", headers={"content-type": "text/plain"})

    page = await fetcher_for(handler).fetch("https://docs.example.org/guide?x=1")
    assert seen["url"] == "https://8.8.8.8/guide?x=1"  # connected to the IP that was checked
    assert seen["host"] == "docs.example.org"          # but the site still sees its own name
    assert page.url == "https://docs.example.org/guide?x=1" and page.text == "hello"


# --- Redirects ------------------------------------------------------------------
async def test_a_redirect_to_a_private_address_is_refused_on_that_hop():
    calls = []

    def handler(request):
        calls.append(request.headers["host"])
        return httpx.Response(302, headers={"location": "https://intranet.example.org/secret"})

    with pytest.raises(FetchRefused) as caught:
        await fetcher_for(handler).fetch("https://docs.example.org/old")
    assert "non-public" in caught.value.message
    assert calls == ["docs.example.org"]  # the private host was never contacted


async def test_a_redirect_to_http_or_a_relative_path_is_handled_safely():
    def to_http(request):
        return httpx.Response(301, headers={"location": "http://other.example.org/"})

    with pytest.raises(FetchRefused, match="only https"):
        await fetcher_for(to_http).fetch("https://docs.example.org/")

    hops = []

    def relative(request):
        hops.append(request.url.path)
        if request.url.path == "/start":
            return httpx.Response(302, headers={"location": "/final"})
        return httpx.Response(200, text="done", headers={"content-type": "text/plain"})

    page = await fetcher_for(relative).fetch("https://docs.example.org/start")
    assert hops == ["/start", "/final"] and page.redirects == ("https://docs.example.org/final",)


async def test_redirect_loops_stop():
    def loop(request):
        return httpx.Response(302, headers={"location": "https://docs.example.org/again"})

    with pytest.raises(FetchRefused, match="too many redirects"):
        await fetcher_for(loop, max_redirects=3).fetch("https://docs.example.org/")


# --- Limits ----------------------------------------------------------------------
async def test_only_text_content_types_are_read():
    with pytest.raises(FetchRefused) as caught:
        await fetcher_for(ok("%PDF-1.4", "application/pdf")).fetch("https://docs.example.org/doc.pdf")
    assert caught.value.kind == "unsupported"

    with pytest.raises(FetchRefused) as caught:
        await fetcher_for(ok("x", "application/octet-stream")).fetch("https://docs.example.org/file")
    assert caught.value.kind == "unsupported"


async def test_a_page_over_the_size_limit_is_cut_and_marked():
    page = await fetcher_for(ok("x" * 5000, "text/plain"), max_bytes=1000).fetch("https://docs.example.org/big")
    assert page.truncated is True and len(page.text) == 1000


async def test_error_statuses_and_timeouts_are_refusals_with_reasons():
    with pytest.raises(FetchRefused, match="HTTP 404"):
        await fetcher_for(lambda r: httpx.Response(404, text="no")).fetch("https://docs.example.org/missing")

    def slow(request):
        raise httpx.ReadTimeout("too slow")

    with pytest.raises(FetchRefused, match="timed out"):
        await fetcher_for(slow).fetch("https://docs.example.org/slow")

    def broken(request):
        raise httpx.ConnectError("no route")

    with pytest.raises(FetchRefused, match="could not connect"):
        await fetcher_for(broken).fetch("https://docs.example.org/down")
