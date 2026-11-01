"""
GitHub tools: search repositories, and inspect one in depth.

    search_github        find repositories by keywords (cheap: one request)
    inspect_repository   read one repository's README and license (two or three requests)

The rules these tools enforce, whatever the model asks
    - Every request is paid from the run's GitHub budget; at the cap, the
      tool refuses and says so.
    - A search query is cleaned to plain keywords and `language:` / `topic:`
      / `in:` (clean_query). Filters that would HIDE awkward results, like
      `license:mit` or `archived:false`, are dropped: later phases must see
      unlicensed and archived options to judge them.
    - A rate limit is reported as a rate limit, never as "no results".
    - What came back is recorded as facts and evidence by code.
"""

import asyncio
import re

from pydantic import BaseModel, Field

from app.evidence.builders import build_repo_evidence
from app.integrations.github_client import GitHubError, GitHubRateLimited, LicenseOutcome, Provenance
from app.models.common import utc_now
from app.models.research import Candidate, SourceFacts
from app.tools.base import Tool, ToolContext, ToolResult, refuse, reply
from app.tools.facts import facts_from_inspection, facts_from_search_hit, facts_summary
from app.graph import events

MAX_QUERY_LENGTH = 120
MAX_KEYWORDS = 6
MAX_QUALIFIERS = 2
ALLOWED_QUALIFIERS = {"language", "topic", "in"}
RESULTS_PER_SEARCH = 8
README_CHARS_FOR_MODEL = 1_000
_URL = re.compile(r"https?://\S+", re.IGNORECASE)
_OPERATORS = {"and", "or", "not"}


def clean_query(text: str) -> str:
    """A safe search query, or "" when nothing usable is left.

    Works one whitespace-separated piece at a time, so a filter that is not
    allowed (`license:mit`, `repo:owner/name`, `stars:>100`) is dropped WHOLE.
    """
    text = _URL.sub(" ", text)
    keywords: list[str] = []
    qualifiers: list[str] = []
    for piece in text.split():
        if ":" in piece:
            name, _, value = piece.partition(":")
            value = re.sub(r"[^A-Za-z0-9_.+#-]", "", value)
            if name.lower() in ALLOWED_QUALIFIERS and value and len(qualifiers) < MAX_QUALIFIERS:
                qualifiers.append(f"{name.lower()}:{value}")
            continue
        word = re.sub(r"[^A-Za-z0-9_.+#-]", "", piece)
        if word.lower() in _OPERATORS or len(word) < 2:
            continue
        if len(keywords) < MAX_KEYWORDS and word.lower() not in {k.lower() for k in keywords}:
            keywords.append(word)
    if not keywords:
        return ""
    return " ".join(keywords + qualifiers)[:MAX_QUERY_LENGTH].strip()


# --- search_github ------------------------------------------------------------------
class SearchGitHubArgs(BaseModel):
    query: str = Field(description="2 to 4 keywords that would appear in a suitable repository's name, description or README. Every word must match, so fewer is better.")
    language: str | None = Field(default=None, description="Optional programming language, e.g. python.")


# How long a tool will wait out a GitHub rate limit by itself. A short wait costs
# nothing; handing the problem to the model costs a whole model call and gives
# it nothing to do. Replaceable in tests.
MAX_TOOL_WAIT_SECONDS = 35.0
wait = asyncio.sleep
# A search that finds nothing is retried with fewer words, this many times.
MAX_RELAXATIONS = 2


def relaxed_queries(query: str) -> list[str]:
    """Shorter versions of a query, for when GitHub finds nothing.

    LEARNING NOTE: GitHub search needs EVERY word to match. Found live: of 22
    searches, 15 returned nothing, because models write 5 to 7 words. Dropping
    the least important (last) words is how a person would retry. Language
    and other filters are kept, and a word equal to the language is dropped.
    """
    words = [w for w in query.split() if ":" not in w]
    filters = [w for w in query.split() if ":" in w]
    language = next((f.partition(":")[2].lower() for f in filters if f.lower().startswith("language:")), None)
    if language:
        words = [w for w in words if w.lower() != language]
    versions = []
    for keep in (3, 2):
        if len(words) > keep:
            versions.append(" ".join([*words[:keep], *filters]))
    return versions[:MAX_RELAXATIONS]


async def _search_with_waiting(github, query: str, ctx: ToolContext):
    """One search; a short rate limit is waited out once. Raises GitHubRateLimited otherwise."""
    try:
        return await github.search_repositories(query, per_page=RESULTS_PER_SEARCH)
    except GitHubRateLimited as limited:
        if limited.wait_seconds > MAX_TOOL_WAIT_SECONDS:
            raise
        ctx.emit(events.rate_limited(service="github", wait_seconds=limited.wait_seconds, will_wait=True))
        await wait(limited.wait_seconds + 1)
        return await github.search_repositories(query, per_page=RESULTS_PER_SEARCH)


async def search_github(args: SearchGitHubArgs, ctx: ToolContext) -> ToolResult:
    query = clean_query(args.query + (f" language:{args.language}" if args.language else ""))
    if not query:
        return refuse("the query had no usable keywords (filters like license: or stars: are not allowed)")
    github = ctx.integrations.github
    attempts = [query]
    outcome = None
    tried = []
    while attempts:
        current = attempts.pop(0)
        if not ctx.budget.take("github"):
            ctx.notes.append("The run's GitHub request budget was used up; some searches were not run.")
            if outcome is None:
                return refuse("the run's GitHub request budget is used up; work with what you have")
            break
        try:
            outcome = await _search_with_waiting(github, current, ctx)
        except GitHubRateLimited as limited:
            ctx.emit(events.rate_limited(service="github", wait_seconds=limited.wait_seconds, will_wait=False))
            ctx.notes.append(f"GitHub rate limit reached during a search (retry in {int(limited.wait_seconds)} s); results are partial.")
            return refuse(f"GitHub rate limit reached; retry in {int(limited.wait_seconds)} s. Do not keep searching.")
        except GitHubError as error:
            return refuse(f"the search failed: {error}")
        if outcome.provenance.requested:
            ctx.emit(events.usage(service="github", mode=github.mode, model=None, tokens=None))
        else:
            ctx.budget.give_back("github")  # answered from the cache: no request was made
        tried.append(current)
        if outcome.candidates:
            break
        if len(tried) == 1:
            attempts = relaxed_queries(query)  # nothing found: retry shorter, without asking the model

    rows = []
    for hit in outcome.candidates:
        facts, item = facts_from_search_hit(hit, github.mode)
        ctx.remember(facts)
        ctx.pending[item.id] = item
        rows.append({**facts_summary(facts), "description": (hit.description or "")[:140], "topics": (hit.topics or [])[:5]})
    shown = tried[-1]
    ctx.emit(events.source_used("github", len(rows)))
    ctx.emit(events.activity(f"GitHub search “{shown}”: {len(rows)} repositories"))
    note = "search facts only; inspect a repository before proposing it"
    if shown != query:
        note = f"nothing matched every word of “{query}”, so a shorter query was used: “{shown}”. " + note
    return reply({"query": shown, "results": rows, "note": note})


SEARCH_GITHUB = Tool(
    name="search_github",
    description="Search GitHub repositories by keywords. Returns name, license, stars, last activity and archived flag "
                "for up to 8 repositories. Costs one GitHub request.",
    args=SearchGitHubArgs, run=search_github,
)


# --- inspect_repository ----------------------------------------------------------------
class InspectRepositoryArgs(BaseModel):
    repo: str = Field(description='The repository as "owner/name".')


async def inspect_repository(args: InspectRepositoryArgs, ctx: ToolContext) -> ToolResult:
    github = ctx.integrations.github
    name = args.repo.strip().removeprefix("https://github.com/").strip("/")
    known = ctx.known("github", name)
    if known is not None and known.inspected:
        return reply({"already_inspected": facts_summary(known)})

    # LEARNING NOTE: spend GitHub's small allowance where it adds something
    #   A search hit already carries the license GitHub detected, which is the
    #   same answer the license endpoint gives. Asking again used a third of
    #   every inspection's requests (60 reads an hour without a token), so
    #   a repository seen in a search costs ONE request (its README); one not
    #   seen in a search needs the details, the README and the license.
    license_known = known is not None and known.license_status in ("detected", "none_detected", "unrecognised")
    needed = 1 if license_known else (2 if known is not None else 3)
    if not ctx.budget.take("github", needed):
        return refuse("the run's GitHub request budget is used up; work with what you have")

    try:
        if known is None:
            candidate = await github.get_repository(name)
            if candidate is None:
                return refuse(f"GitHub has no repository named {name}")
            ctx.emit(events.usage(service="github", mode=github.mode, model=None, tokens=None))
        else:
            candidate = _candidate_from_facts(known, ctx)
    except GitHubRateLimited as limited:
        ctx.notes.append(f"GitHub rate limit reached while inspecting {name}.")
        return refuse(f"GitHub rate limit reached; retry in {int(limited.wait_seconds)} s")
    except GitHubError as error:
        return refuse(f"could not read {name}: {error}")

    real_requests = 1 if known is None else 0  # the repository details request, when it was needed

    async def attempt(call):
        nonlocal real_requests
        try:
            outcome = await call(candidate.repo)
        except GitHubRateLimited as limited:
            real_requests += 1
            ctx.notes.append(f"GitHub rate limit reached: the license or README of {candidate.repo} was not retrieved.")
            return None, f"rate limit reached, retry in {int(limited.wait_seconds)} s"
        except GitHubError as error:
            real_requests += 1
            return None, str(error)
        if outcome.provenance.requested:
            real_requests += 1
            ctx.emit(events.usage(service="github", mode=github.mode, model=None, tokens=None))
        return outcome, None

    readme, readme_error = await attempt(github.get_readme)
    if license_known:
        license_ = LicenseOutcome(
            spdx_id=known.license, name=None, found=known.license is not None,
            provenance=Provenance(retrieved_at=candidate.retrieved_at, from_cache=False, requested=False),
        )
        license_error = None
    else:
        license_, license_error = await attempt(github.get_license)
    ctx.budget.give_back("github", max(0, needed - real_requests))  # cached answers were free
    repo, items = build_repo_evidence(candidate, readme=readme, readme_error=readme_error,
                                      license_=license_, license_error=license_error, mode=github.mode)
    for item in items:
        ctx.publish(item)
    ctx.repos.append(repo)
    facts = facts_from_inspection(repo)
    ctx.remember(facts)
    ctx.emit(events.source_used("github", 1))
    ctx.emit(events.activity(f"Inspected {repo.repo}: license {facts.license or facts.license_status.replace('_', ' ')}"))
    return reply({**facts_summary(facts), "description": repo.description,
                  "readme_excerpt": (readme.text or "")[:README_CHARS_FOR_MODEL] if readme and readme.found else None,
                  "notes": repo.notes})


def _candidate_from_facts(known: SourceFacts, ctx: ToolContext) -> Candidate:
    """Rebuild the search hit we already have, keeping its original retrieval date."""
    first = ctx.pending.get(known.evidence_ids[0]) if known.evidence_ids else None
    return Candidate(
        repo=known.reference, url=known.url, description=known.description, license=known.license,
        archived=known.archived, stars=known.stars, last_push=known.last_activity,
        retrieved_at=first.retrieved_at if first else utc_now(), mode=known.mode,
    )


INSPECT_REPOSITORY = Tool(
    name="inspect_repository",
    description="Read one GitHub repository in depth: its README (start) and its license file. "
                "Do this before proposing a GitHub repository. Costs two or three GitHub requests.",
    args=InspectRepositoryArgs, run=inspect_repository,
)
