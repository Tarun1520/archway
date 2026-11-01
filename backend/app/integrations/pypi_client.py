"""
PyPIClient: facts about a Python package from the Python Package Index.

What it does
    get_package(name)   GET https://pypi.org/pypi/{name}/json
    Returns the summary, latest version and release date, the declared
    license, and the project's links (often including its source repository).

Verified against PyPI's documentation (2026-10-14)
    The JSON API answers with `info` (name, summary, license,
    license_expression, classifiers, version, project_urls, requires_python)
    and `urls` (the latest release's files, each with upload_time_iso_8601).
    PyPI has NO search API, so this client looks up a NAMED package. Agents
    find names on GitHub or from their own knowledge, and must then verify
    them here; a name that does not exist simply comes back "not found".

How a license is read (in this order)
    1. `license_expression` (the modern SPDX field), if set
    2. a "License :: ..." classifier
    3. a short `license` text, one line of up to 120 characters (a long one is
       usually the whole license file). Found live: PyMuPDF declares its AGPL
       license only here, in 64 characters.
    Nothing found means "none declared", which is reported as such.
"""

import json
import re
from dataclasses import dataclass
from datetime import datetime

from app.integrations.github_client import Provenance
from app.integrations.http_json import JsonHttp, RegistryError
from app.models.common import ServiceMode

PYPI_BASE = "https://pypi.org"
PACKAGE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")


@dataclass(frozen=True)
class PackageInfo:
    name: str
    url: str  # the package's page
    summary: str | None
    version: str | None
    license: str | None
    released: datetime | None  # when the latest version was uploaded
    source_url: str | None  # a link to its code, if the package lists one
    provenance: Provenance
    description: str | None = None  # the long description (usually the README), as published; cleaned before use


def _license_of(info: dict) -> str | None:
    expression = info.get("license_expression")
    if isinstance(expression, str) and expression.strip():
        return expression.strip()
    for classifier in info.get("classifiers") or []:
        if isinstance(classifier, str) and classifier.startswith("License ::"):
            return classifier.split("::")[-1].strip()
    text = info.get("license")
    if isinstance(text, str) and text.strip() and "\n" not in text.strip() and len(text.strip()) <= 120:
        return text.strip()
    return None


def _source_url(info: dict) -> str | None:
    urls = info.get("project_urls") or {}
    if isinstance(urls, dict):
        for label in ("Source", "Source Code", "Repository", "Code", "GitHub", "Homepage"):
            for key, value in urls.items():
                if key.lower() == label.lower() and isinstance(value, str) and value.startswith("https://"):
                    return value
    return None


class PyPIClient:
    def __init__(self, http: JsonHttp, *, mode: ServiceMode):
        self._http = http
        self.mode = mode

    async def get_package(self, name: str) -> PackageInfo | None:
        """The package's facts, or None when PyPI has no package by that name."""
        if not PACKAGE_NAME.match(name):
            raise RegistryError(f"{name!r} is not a package name")
        status, body, provenance = await self._http.get(f"/pypi/{name}/json")
        if status == 404:
            return None
        try:
            data = json.loads(body)
            info = data["info"]
        except (ValueError, KeyError, TypeError) as error:
            raise RegistryError("PyPI's reply was not the expected JSON") from error

        released = None
        files = data.get("urls") or []
        times = [f.get("upload_time_iso_8601") for f in files if isinstance(f, dict) and f.get("upload_time_iso_8601")]
        if times:
            try:
                released = datetime.fromisoformat(max(times).replace("Z", "+00:00"))
            except ValueError:
                released = None
        package = info.get("name") or name
        return PackageInfo(
            name=package, url=f"https://pypi.org/project/{package}/", summary=info.get("summary") or None,
            version=info.get("version") or None, license=_license_of(info), released=released,
            source_url=_source_url(info), provenance=provenance,
            description=info.get("description") if isinstance(info.get("description"), str) else None,
        )
