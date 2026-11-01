"""
Package-registry tools: check Python (PyPI) and JavaScript (npm) packages.

    lookup_pypi   facts about a NAMED Python package (PyPI has no search)
    search_npm    find JavaScript packages by keywords
    lookup_npm    facts about a NAMED npm package

Why "lookup" matters
    A model may remember a library's name. That memory can be wrong or out of
    date. A lookup is how the name is VERIFIED: it exists, this is its license,
    this is when it was last released. Only looked-up packages can be proposed.
"""

from pydantic import BaseModel, Field

from app.graph import events
from app.integrations.http_json import RegistryError, RegistryRateLimited
from app.tools.base import Tool, ToolContext, ToolResult, refuse, reply
from app.tools.facts import facts_from_npm, facts_from_pypi, facts_summary


async def _with_downloads(facts, ctx: ToolContext):
    """Add the monthly download count when it can be known (best effort, free, never blocks a lookup)."""
    if ctx.integrations.adoption is None:
        return facts
    downloads = await ctx.integrations.adoption.downloads_last_month(facts.kind, facts.reference)
    return facts.model_copy(update={"downloads_last_month": downloads}) if downloads is not None else facts


class LookupArgs(BaseModel):
    name: str = Field(description="The exact package name.")


async def lookup_pypi(args: LookupArgs, ctx: ToolContext) -> ToolResult:
    if not ctx.budget.take("registry"):
        return refuse("the run's package-lookup budget is used up")
    pypi = ctx.integrations.pypi
    try:
        package = await pypi.get_package(args.name.strip())
    except RegistryRateLimited:
        return refuse("PyPI rate limit reached; try later")
    except RegistryError as error:
        return refuse(str(error))
    ctx.emit(events.source_used("pypi", 0 if package is None else 1))
    if package is None:
        return reply({"found": False, "name": args.name, "note": "no package by this name on PyPI"})
    facts, item = facts_from_pypi(package, pypi.mode)
    facts = await _with_downloads(facts, ctx)
    ctx.remember(facts)
    ctx.publish(item)
    ctx.emit(events.activity(f"PyPI: checked {package.name} (license {package.license or 'not declared'})"))
    return reply({"found": True, **facts_summary(facts), "summary": package.summary, "version": package.version,
                  "source_url": package.source_url})


class SearchNpmArgs(BaseModel):
    text: str = Field(description="Keywords describing what the package should do.")


async def search_npm(args: SearchNpmArgs, ctx: ToolContext) -> ToolResult:
    if not ctx.budget.take("registry"):
        return refuse("the run's package-lookup budget is used up")
    try:
        hits, _ = await ctx.integrations.npm.search(args.text, size=8)
    except RegistryRateLimited:
        return refuse("npm rate limit reached; try later")
    except RegistryError as error:
        return refuse(str(error))
    ctx.emit(events.source_used("npm", len(hits)))
    ctx.emit(events.activity(f"npm search “{args.text[:60]}”: {len(hits)} packages"))
    return reply({"results": [
        {"name": h.name, "description": (h.description or "")[:140], "version": h.version,
         "last_release": h.date.date().isoformat() if h.date else None, "repository": h.repository}
        for h in hits
    ], "note": "search results only; look a package up before proposing it"})


async def lookup_npm(args: LookupArgs, ctx: ToolContext) -> ToolResult:
    if not ctx.budget.take("registry"):
        return refuse("the run's package-lookup budget is used up")
    npm = ctx.integrations.npm
    try:
        package = await npm.get_package(args.name.strip())
    except RegistryRateLimited:
        return refuse("npm rate limit reached; try later")
    except RegistryError as error:
        return refuse(str(error))
    ctx.emit(events.source_used("npm", 0 if package is None else 1))
    if package is None:
        return reply({"found": False, "name": args.name, "note": "no package by this name on npm"})
    facts, item = facts_from_npm(package, npm.mode)
    facts = await _with_downloads(facts, ctx)
    ctx.remember(facts)
    ctx.publish(item)
    ctx.emit(events.activity(f"npm: checked {package.name} (license {package.license or 'not declared'})"))
    return reply({"found": True, **facts_summary(facts), "description": package.description,
                  "version": package.version, "repository": package.repository})


LOOKUP_PYPI = Tool(
    name="lookup_pypi",
    description="Check a Python package by its exact name on PyPI: summary, latest version and release date, "
                "declared license, source link. Use it to verify a library you know of before proposing it.",
    args=LookupArgs, run=lookup_pypi,
)
SEARCH_NPM = Tool(
    name="search_npm",
    description="Search the npm registry for JavaScript/TypeScript packages by keywords.",
    args=SearchNpmArgs, run=search_npm,
)
LOOKUP_NPM = Tool(
    name="lookup_npm",
    description="Check an npm package by its exact name: description, latest version, declared license, repository.",
    args=LookupArgs, run=lookup_npm,
)
