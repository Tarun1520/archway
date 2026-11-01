"""
NpmClient: finding and checking JavaScript packages in the npm registry.

What it does
    search(text)        GET https://registry.npmjs.org/-/v1/search?text=...&size=...
    get_package(name)   GET https://registry.npmjs.org/{name}/latest

Verified against the registry's API document (2026-10-14)
    Search answers `objects[]`, each with `package` (name, version,
    description, keywords, date, links.repository ...) and `score`.
    `/{name}/latest` returns the latest version's package.json data,
    including its `license` field.
"""

import json
import re
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import quote

from app.integrations.github_client import Provenance
from app.integrations.http_json import JsonHttp, RegistryError
from app.models.common import ServiceMode

NPM_BASE = "https://registry.npmjs.org"
PACKAGE_NAME = re.compile(r"^(@[a-z0-9][a-z0-9._~-]*/)?[a-z0-9][a-z0-9._~-]{0,213}$")


@dataclass(frozen=True)
class NpmHit:
    name: str
    version: str | None
    description: str | None
    date: datetime | None
    repository: str | None


@dataclass(frozen=True)
class NpmPackage:
    name: str
    url: str
    version: str | None
    description: str | None
    license: str | None
    repository: str | None
    provenance: Provenance


def _date(value) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _repository_url(value) -> str | None:
    url = value.get("url") if isinstance(value, dict) else value
    if not isinstance(url, str):
        return None
    url = url.removeprefix("git+").removesuffix(".git")
    return url if url.startswith("https://") else None


class NpmClient:
    def __init__(self, http: JsonHttp, *, mode: ServiceMode):
        self._http = http
        self.mode = mode

    async def search(self, text: str, *, size: int = 10) -> tuple[list[NpmHit], Provenance]:
        status, body, provenance = await self._http.get("/-/v1/search", {"text": text[:120], "size": size})
        if status != 200:
            raise RegistryError(f"npm search answered HTTP {status}")
        try:
            objects = json.loads(body)["objects"]
        except (ValueError, KeyError, TypeError) as error:
            raise RegistryError("npm's search reply was not the expected JSON") from error
        hits = []
        for item in objects:
            package = item.get("package") if isinstance(item, dict) else None
            if not isinstance(package, dict) or not isinstance(package.get("name"), str):
                continue
            links = package.get("links") or {}
            hits.append(NpmHit(
                name=package["name"], version=package.get("version"), description=package.get("description"),
                date=_date(package.get("date")), repository=_repository_url(links.get("repository")),
            ))
        return hits, provenance

    async def get_package(self, name: str) -> NpmPackage | None:
        if not PACKAGE_NAME.match(name):
            raise RegistryError(f"{name!r} is not an npm package name")
        status, body, provenance = await self._http.get(f"/{quote(name, safe='@')}/latest")
        if status == 404:
            return None
        try:
            data = json.loads(body)
        except ValueError as error:
            raise RegistryError("npm's package reply was not the expected JSON") from error
        license_value = data.get("license")
        if isinstance(license_value, dict):
            license_value = license_value.get("type")
        return NpmPackage(
            name=data.get("name") or name, url=f"https://www.npmjs.com/package/{name}", version=data.get("version"),
            description=data.get("description"), license=license_value if isinstance(license_value, str) else None,
            repository=_repository_url(data.get("repository")), provenance=provenance,
        )
