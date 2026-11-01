"""
Adoption signals: how many people actually download a package.

What this file does
    npm   GET https://api.npmjs.org/downloads/point/last-month/{name}  -> {"downloads": N}
    PyPI  GET https://pypistats.org/api/packages/{name}/recent       -> {"data": {"last_month": N}}
    Both are free and need no key. A failed or missing answer is None
    ("not known"), never zero.

Why it exists
    Stars only exist for GitHub. For packages, monthly downloads are the
    clearest sign that something is a real, used building block rather than
    a weekend experiment. It is shown beside each component and used to
    break ties when ranking; it never overrides the relevance judge.
"""

import json
from urllib.parse import quote

from app.integrations.http_json import JsonHttp, RegistryError

NPM_DOWNLOADS_BASE = "https://api.npmjs.org"
PYPISTATS_BASE = "https://pypistats.org"


class AdoptionClient:
    def __init__(self, *, npm: JsonHttp, pypi: JsonHttp):
        self._npm = npm
        self._pypi = pypi

    async def downloads_last_month(self, kind: str, name: str) -> int | None:
        try:
            if kind == "npm":
                status, body, _ = await self._npm.get(f"/downloads/point/last-month/{quote(name, safe='@')}")
                value = json.loads(body).get("downloads") if status == 200 else None
            elif kind == "pypi":
                status, body, _ = await self._pypi.get(f"/api/packages/{quote(name.lower())}/recent")
                value = (json.loads(body).get("data") or {}).get("last_month") if status == 200 else None
            else:
                return None
        except (RegistryError, ValueError, AttributeError):
            return None
        return value if isinstance(value, int) and value >= 0 else None
