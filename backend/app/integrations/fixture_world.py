"""
The recorded "world" used when GITHUB_MODE=fixture: GitHub and a few doc pages.

What this file does
    Answers the same HTTP requests the real services would, from the file
    backend/fixtures/github/world.json. The client code cannot tell the
    difference, which is the point (LEARNING_GUIDE.md topic 33).

IMPORTANT: this is not GitHub
    Every repository in that file is invented. The search is a simple
    keyword match, and when nothing matches it returns the whole set (so an
    offline demo always has something to show). Results are labelled
    FIXTURE DATA in the UI and never mixed with live results.

The set deliberately includes the awkward cases the evaluation needs:
    a repository with no license, an archived one, a GPL one, one whose
    README tries to give the model instructions, and one with no README.

How it plugs in
    app/research/factory.py uses `github_fixture_transport` and
    `docs_fixture_transport`.
"""

import json
import re
from functools import lru_cache
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import httpx

WORLD_FILE = Path(__file__).resolve().parents[2] / "fixtures" / "github" / "world.json"

# A made-up public address for the fixture documentation host, so the same
# "is this address public?" check runs in fixture mode as in live mode.
FIXTURE_DOCS_IP = "93.184.216.34"
FIXTURE_DOCS_HOST = "fixture-docs.example"


@lru_cache
def load_world() -> dict:
    return json.loads(WORLD_FILE.read_text(encoding="utf-8"))


def _search_item(repo: dict) -> dict:
    license_object = (
        {"key": repo["license"].lower(), "name": repo["license_name"], "spdx_id": repo["license"], "url": None}
        if repo["license"] else None
    )
    return {
        "full_name": repo["full_name"],
        "html_url": f"https://github.com/{repo['full_name']}",
        "description": repo["description"],
        "language": repo["language"],
        "topics": repo["topics"],
        "license": license_object,
        "archived": repo["archived"],
        "pushed_at": repo["pushed_at"],
        "stargazers_count": repo["stargazers_count"],
        "homepage": repo["homepage"],
    }


def _terms(query: str) -> tuple[list[str], dict[str, str]]:
    keywords, qualifiers = [], {}
    for token in query.split():
        if ":" in token:
            name, _, value = token.partition(":")
            qualifiers[name.lower()] = value.lower()
        else:
            keywords.append(token.lower())
    return keywords, qualifiers


def _search(query: str, per_page: int) -> dict:
    keywords, qualifiers = _terms(query)
    scored = []
    for repo in load_world()["repos"]:
        if "language" in qualifiers and (repo["language"] or "").lower() != qualifiers["language"]:
            continue
        if "topic" in qualifiers and qualifiers["topic"] not in repo["topics"]:
            continue
        haystack = " ".join([repo["full_name"], repo["description"] or "", " ".join(repo["topics"]), repo["readme"] or ""]).lower()
        score = sum(1 for word in keywords if word in haystack)
        if score or not keywords:
            scored.append((score, repo))
    # Nothing matched: nothing is returned, as a real search would. (It used to return the whole recorded set,
    # which made the "weak evidence" evaluation scenario impossible: every search found something.)
    scored.sort(key=lambda pair: (-pair[0], -pair[1]["stargazers_count"]))
    items = [_search_item(repo) for _, repo in scored[:per_page]]
    return {"total_count": len(scored), "incomplete_results": False, "items": items}


def _github_handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path == "/search/repositories":
        params = parse_qs(urlparse(str(request.url)).query)
        query = params.get("q", [""])[0]
        per_page = int(params.get("per_page", ["30"])[0])
        return httpx.Response(200, json=_search(query, per_page))

    whole = re.fullmatch(r"/repos/([^/]+/[^/]+)", path)
    if whole:
        repo = next((r for r in load_world()["repos"] if r["full_name"] == whole.group(1)), None)
        return httpx.Response(200, json=_search_item(repo)) if repo else httpx.Response(404, json={"message": "Not Found"})

    match = re.fullmatch(r"/repos/([^/]+/[^/]+)/(readme|license)", path)
    if match:
        full_name, kind = match.groups()
        repo = next((r for r in load_world()["repos"] if r["full_name"] == full_name), None)
        if repo is None:
            return httpx.Response(404, json={"message": "Not Found"})
        if kind == "readme":
            if repo["readme"] is None:
                return httpx.Response(404, json={"message": "Not Found"})
            return httpx.Response(200, text=repo["readme"], headers={"content-type": "text/plain; charset=utf-8"})
        if repo["license"] is None:
            return httpx.Response(404, json={"message": "Not Found"})
        return httpx.Response(200, json={
            "name": "LICENSE", "path": "LICENSE",
            "license": {"key": repo["license"].lower(), "name": repo["license_name"], "spdx_id": repo["license"]},
        })
    return httpx.Response(404, json={"message": "Not Found"})


def _docs_handler(request: httpx.Request) -> httpx.Response:
    # The fetcher connects by IP address (see safe_fetch.py), so rebuild the
    # public URL from the Host header to look the page up.
    host = request.headers.get("host", "")
    url = f"https://{host}{request.url.path}"
    page = load_world()["docs"].get(url)
    if page is None:
        return httpx.Response(404, text="not found", headers={"content-type": "text/plain"})
    return httpx.Response(200, text=page["body"], headers={"content-type": page["content_type"]})


def github_fixture_transport() -> httpx.MockTransport:
    return httpx.MockTransport(_github_handler)


def docs_fixture_transport() -> httpx.MockTransport:
    return httpx.MockTransport(_docs_handler)


async def fixture_resolver(host: str) -> list[str]:
    """Knows one documentation host. Every other name 'does not resolve'.

    Literal IP addresses and names like "localhost" are decided by the safety
    checks before this is asked, so they are refused in fixture mode too.
    """
    return [FIXTURE_DOCS_IP] if host == FIXTURE_DOCS_HOST else []


# --- Package registries (fixture) ----------------------------------------------------
def _pypi_handler(request: httpx.Request) -> httpx.Response:
    match = re.fullmatch(r"/pypi/([^/]+)/json", request.url.path)
    package = load_world()["packages"]["pypi"].get(match.group(1)) if match else None
    if package is None:
        return httpx.Response(404, json={"message": "Not Found"})
    name = match.group(1)
    return httpx.Response(200, json={
        "info": {"name": name, "summary": package["summary"], "version": package["version"],
                 "license_expression": package["license_expression"], "license": None, "classifiers": [],
                 "project_urls": {"Source": package["source"]} if package["source"] else {}},
        "urls": [{"upload_time_iso_8601": package["released"]}],
    })


def _npm_handler(request: httpx.Request) -> httpx.Response:
    packages = load_world()["packages"]["npm"]
    if request.url.path == "/-/v1/search":
        words = [w.lower() for w in request.url.params.get("text", "").split()]
        hits = [(name, info) for name, info in packages.items()
                if not words or any(w in f"{name} {info['description']}".lower() for w in words)]
        return httpx.Response(200, json={"total": len(hits), "objects": [
            {"package": {"name": name, "version": info["version"], "description": info["description"], "date": info["date"],
                         "links": {"repository": info["repository"]}}, "score": {"final": 0.5}}
            for name, info in hits
        ]})
    match = re.fullmatch(r"/([^/]+)/latest", request.url.path)
    info = packages.get(match.group(1)) if match else None
    if info is None:
        return httpx.Response(404, json={"error": "Not found"})
    return httpx.Response(200, json={"name": match.group(1), "version": info["version"], "description": info["description"],
                                     "license": info["license"], "repository": {"url": info["repository"]} if info["repository"] else None})


def pypi_fixture_transport() -> httpx.MockTransport:
    return httpx.MockTransport(_pypi_handler)


def npm_fixture_transport() -> httpx.MockTransport:
    return httpx.MockTransport(_npm_handler)
