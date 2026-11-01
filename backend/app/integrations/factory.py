"""
Choosing the research integrations (GitHub, PyPI, npm, page fetcher) from the settings.

This is the ONLY place that decides whether research talks to the real
internet or to recorded data (compare app/llm/factory.py).

    github_mode = "live"      the real services, with a local cache
    github_mode = "fixture"   recorded data only, no network, no cache (so
                              demo data is never saved where live data could
                              pick it up)

The one setting covers all research sources: they are all "the outside
world the research team reads".
"""

from dataclasses import dataclass
from datetime import timedelta

from app.config.settings import Settings
from app.integrations.adoption_client import NPM_DOWNLOADS_BASE, PYPISTATS_BASE, AdoptionClient
from app.integrations.cache import NoCache, SqliteCache
from app.integrations.fixture_world import (
    docs_fixture_transport,
    fixture_resolver,
    github_fixture_transport,
    npm_fixture_transport,
    pypi_fixture_transport,
)
from app.integrations.discussion_client import DiscussionClient
from app.integrations.github_client import GitHubClient
from app.integrations.http_json import JsonHttp
from app.integrations.npm_client import NPM_BASE, NpmClient
from app.integrations.pypi_client import PYPI_BASE, PyPIClient
from app.integrations.safe_fetch import SafeFetcher
from app.integrations.web_search_client import WebSearchClient

CACHE_TTL = timedelta(hours=24)


@dataclass(frozen=True)
class Integrations:
    github: GitHubClient
    pypi: PyPIClient
    npm: NpmClient
    fetcher: SafeFetcher
    discussion: DiscussionClient
    web_search: WebSearchClient | None = None  # only when BRAVE_API_KEY is set
    adoption: AdoptionClient | None = None  # download counts; live mode only


def build_integrations(settings: Settings) -> Integrations:
    if settings.github_mode == "fixture":
        return Integrations(
            github=GitHubClient(mode="fixture", transport=github_fixture_transport(), cache=NoCache()),
            pypi=PyPIClient(JsonHttp(base_url=PYPI_BASE, service="PyPI", transport=pypi_fixture_transport()), mode="fixture"),
            npm=NpmClient(JsonHttp(base_url=NPM_BASE, service="npm", transport=npm_fixture_transport()), mode="fixture"),
            fetcher=SafeFetcher(resolver=fixture_resolver, transport=docs_fixture_transport()),
            discussion=DiscussionClient(mode="fixture"),
        )
    cache = SqliteCache(settings.database_path, CACHE_TTL)
    token = settings.github_token.get_secret_value() if settings.github_token else None
    return Integrations(
        github=GitHubClient(mode="live", token=token, cache=cache),
        pypi=PyPIClient(JsonHttp(base_url=PYPI_BASE, service="PyPI", cache=cache), mode="live"),
        npm=NpmClient(JsonHttp(base_url=NPM_BASE, service="npm", cache=cache), mode="live"),
        fetcher=SafeFetcher(),
        discussion=DiscussionClient(mode="live"),
        web_search=WebSearchClient(api_key=settings.brave_api_key.get_secret_value()) if settings.brave_api_key else None,
        adoption=AdoptionClient(
            npm=JsonHttp(base_url=NPM_DOWNLOADS_BASE, service="npm downloads", cache=cache),
            pypi=JsonHttp(base_url=PYPISTATS_BASE, service="pypistats", cache=cache),
        ),
    )
