"""
Report tools: how an agent hands its work back to the team.

Each agent finishes by calling ONE of these ("terminal" tools). The tool
checks the report before accepting it. If something is wrong, the agent is
told exactly what and gets another turn to fix it.

    record_capabilities   capability analyst  the capabilities and their approaches
    submit_components     component scout     options for one capability
    submit_projects       project scout       whole projects similar to the idea
    submit_review         reviewer            is the research complete? what is missing?
    submit_fit            relevance judge     how relevant is each proposed component?

The most important rule: you can only propose what you looked at
    A component or project must be a source a tool actually retrieved in this
    run (searched, inspected, or looked up). A name remembered by the model but
    never verified is dropped (and the whole report refused if nothing is
    verified). Facts such as the license are then copied from
    what the tool retrieved, never from the agent's words.
"""

import difflib
import hashlib
import re
from typing import Literal

from pydantic import BaseModel, Field

from app.models.research import Capability, ComponentCandidate, ReviewGap, ReviewVerdict, SimilarProject
from app.tools.base import Tool, ToolContext, ToolResult, refuse, reply

MAX_CAPABILITIES = 6
MAX_CORE = 4
MAX_APPROACHES = 5
MAX_COMPONENTS = 6
MAX_PROJECTS = 3
APPROACH_LABEL_LENGTH = 140
# Found live: "cost-aware orchestration" drew in rate limiters and feature flags.
_QUALITY_WORDS = re.compile(r"cost|privacy|security|secure|reliab|scalab|performance|compliance|observab|monitoring", re.I)
_LAYER_WORDS = re.compile(r"\b(front[ -]?end|back[ -]?end|app shell|api layer)\b|_(frontend|backend)\b|\b(frontend|backend)_", re.I)


def resolve_approach(text: str | None, approaches: list[str]) -> str | None:
    """Which of the capability's listed approaches a scout meant, or None.

    Found live: the approach was free text, and models reword it a little, so
    3 of 13 components were shown as "no verified option" for the very
    approach they covered. Matching is done here: an exact match, then "A2" or
    "2", then the closest wording.
    """
    if not text or not approaches:
        return None
    wanted = " ".join(text.lower().split())
    for approach in approaches:
        if " ".join(approach.lower().split()) == wanted:
            return approach
    number = re.fullmatch(r"(?:a|approach)?\s*#?(\d+)\s*[:.)]?", wanted)
    if number and 1 <= int(number.group(1)) <= len(approaches):
        return approaches[int(number.group(1)) - 1]
    best, best_score = None, 0.0
    for approach in approaches:
        lowered = " ".join(approach.lower().split())
        score = difflib.SequenceMatcher(None, wanted, lowered).ratio()
        if wanted[:40] == lowered[:40] or lowered.startswith(wanted) or wanted.startswith(lowered):
            score = max(score, 0.9)
        if score > best_score:
            best, best_score = approach, score
    return best if best_score >= 0.5 else None


# --- record_capabilities -------------------------------------------------------------
class CapabilityIn(BaseModel):
    name: str = Field(description="Short name of the technical capability.")
    need: str = Field(description="What the product needs it for, in the brief's terms.")
    requirement_ids: list[str] = Field(default_factory=list, description="Brief requirement ids it serves, e.g. REQ-2.")
    approaches: list[str] = Field(description="The distinct approaches worth comparing (2 to 4 when they exist). Each a short phrase of at most 12 words.")
    search_hints: list[str] = Field(default_factory=list, description="Keywords a scout can start searching with.")
    priority: Literal["core", "supporting"] = Field(description='"core" for a stage of the product\'s central job, '
                                                    '"supporting" for what helps around it.')


class RecordCapabilitiesArgs(BaseModel):
    capabilities: list[CapabilityIn]
    plain_product_logic: list[str] = Field(
        default_factory=list,
        description="Ids of must-have requirements that no open-source component could help with: just the product's own logic.",
    )


def _plain_name(name: str) -> str:
    """Drop an id the model put in front of a name ("CAP-1: Parsing" -> "Parsing").

    Found live: ids are assigned by code, but a model sometimes writes its own
    into the name, which then showed twice in the UI.
    """
    return re.sub(r"^\s*CAP-\d+\s*[:\-\u2013]*\s*", "", name).strip() or name.strip()


async def record_capabilities(args: RecordCapabilitiesArgs, ctx: ToolContext) -> ToolResult:
    items = args.capabilities
    for item in items:
        item.name = _plain_name(item.name)
    if not 1 <= len(items) <= MAX_CAPABILITIES:
        return refuse(f"record between 1 and {MAX_CAPABILITIES} capabilities (you sent {len(items)})")
    names = [item.name.strip().lower() for item in items]
    if len(set(names)) != len(names) or not all(names):
        return refuse("every capability needs a name, and names must be different")
    for item in items:
        approaches = [a.strip() for a in item.approaches if a.strip()]
        if not 1 <= len(approaches) <= MAX_APPROACHES:
            return refuse(f"capability '{item.name}' needs 1 to {MAX_APPROACHES} approaches")
        if not item.need.strip():
            return refuse(f"capability '{item.name}' needs a 'need'")

    # LEARNING NOTE: every must-have must be looked at (found live)
    #   Capabilities came back that left whole requirements unserved (for
    #   example the voice of a phone call), so nothing was ever searched for
    #   them. Each must-have has to be given to a capability, or declared plain
    #   product logic. The check refuses ONCE, so a stubborn model still
    #   produces a result; the unassigned ones are then noted.
    core = [item for item in items if item.priority == "core"]
    if not 1 <= len(core) <= MAX_CORE:
        return refuse(f"mark 1 to {MAX_CORE} capabilities as core: the stages of the product's central job "
                      f"(you marked {len(core)})")
    must = {r.id: r.text for r in ctx.board.brief.must_have}
    served = {r for item in items for r in item.requirement_ids} | set(args.plain_product_logic)
    unserved = [i for i in must if i not in served]
    # Found live: capabilities named after a layer of the app ("mobile frontend",
    # "backend pipeline") pull in generic plumbing. A capability names a function.
    layered = [item.name for item in items if _LAYER_WORDS.search(item.name)]
    qualities = [item.name for item in items if _QUALITY_WORDS.search(item.name) and item.name not in layered]
    if (unserved or layered or qualities) and not ctx.assignment.get("coverage_refused"):
        ctx.assignment["coverage_refused"] = True
        problems = []
        if unserved:
            listing = "; ".join(f"{i}: {must[i][:90]}" for i in unserved[:8])
            problems.append("these must-have requirements are not in any capability: " + listing +
                            ". Give each to a capability that serves it (add one if needed), or list its id in "
                            "plain_product_logic if no existing component could help with it")
        if layered:
            problems.append("these capabilities are named after a layer of the app, not a function: " + ", ".join(layered) +
                            ". Name the technical job instead (what goes in and what comes out), or drop the capability "
                            "if it is only the app's own screens or endpoints")
        if qualities:
            problems.append("these capabilities name a quality, not a function: " + ", ".join(qualities) +
                            ". Cost, privacy, security, reliability and performance are requirements that shape which "
                            "approaches fit; fold them into the capabilities they constrain instead")
        return refuse(". Also: ".join(problems) + ".")
    if unserved:
        ctx.notes.append("Requirements no capability serves: " + ", ".join(unserved))

    real_ids = {r.id for r in ctx.board.brief.must_have + ctx.board.brief.nice_to_have}
    existing = {c.name.strip().lower(): c.id for c in ctx.board.capabilities}
    used = set(existing.values())
    capabilities = []
    for item in items:
        cap_id = existing.get(item.name.strip().lower())
        if cap_id is None:
            number = 1
            while f"CAP-{number}" in used:
                number += 1
            cap_id = f"CAP-{number}"
            used.add(cap_id)
        capabilities.append(Capability(
            id=cap_id, name=item.name.strip()[:80], need=item.need.strip()[:300],
            requirement_ids=[r for r in item.requirement_ids if r in real_ids],
            approaches=[a.strip()[:APPROACH_LABEL_LENGTH] for a in item.approaches if a.strip()][:MAX_APPROACHES],
            search_hints=[h.strip()[:60] for h in item.search_hints if h.strip()][:6],
            priority=item.priority,
        ))
    capabilities.sort(key=lambda c: c.priority != "core")  # core first, otherwise in the analyst's order
    ctx.outcome = {"capabilities": [c.model_dump(mode="json") for c in capabilities]}
    return reply({"recorded": [c.id for c in capabilities]}, terminal=True)


# --- submit_components ---------------------------------------------------------------
class ComponentIn(BaseModel):
    source: Literal["github", "pypi", "npm"]
    reference: str = Field(description='"owner/name" for GitHub, otherwise the exact package name.')
    name: str
    # Required, not optional: found live that the model leaves optional fields
    # out, and without it the UI cannot group options by approach.
    approach: str = Field(description='Which listed approach it represents: its number ("A2") or its exact wording.')
    provides: str = Field(description="What it would give the project.")
    fit_notes: str = Field(description="Why it might fit this brief, based on what you read.")
    concerns: list[str] = Field(default_factory=list, description="Limitations you noticed.")


class SubmitComponentsArgs(BaseModel):
    components: list[ComponentIn]
    summary: str = Field(description="Two or three sentences for the team lead: what you covered and what is missing.")


def identity(facts) -> str:
    """What a component IS, whichever registry it was found through.

    A package and its GitHub repository are one component: an npm or PyPI
    package that names its GitHub repo has that repo as its identity. Found
    live: Multer and BullMQ were each shown twice, once from npm, once from GitHub.
    """
    if facts.kind == "github":
        return f"github:{facts.reference.lower()}"
    if facts.source_repo:
        return f"github:{facts.source_repo.lower()}"
    return f"{facts.kind}:{facts.reference.lower()}"


def merge_duplicates(verified: list, known_identities: set[str]) -> tuple[list, list[str]]:
    """Keep one entry per identity. A package beats its bare GitHub repo (it has
    downloads and a release); the repo's stars are carried over. Anything already
    proposed for this capability is skipped. Returns (kept, names skipped)."""
    by_identity: dict[str, tuple] = {}
    skipped: list[str] = []
    for item, facts in verified:
        key = identity(facts)
        if key in known_identities:
            skipped.append(item.name)
            continue
        if key not in by_identity:
            by_identity[key] = (item, facts)
            continue
        kept_item, kept_facts = by_identity[key]
        package, repo = ((item, facts), (kept_item, kept_facts)) if kept_facts.kind == "github" else ((kept_item, kept_facts), (item, facts))
        merged = package[1].model_copy(update={
            "stars": package[1].stars if package[1].stars is not None else repo[1].stars,
            "evidence_ids": list(dict.fromkeys([*package[1].evidence_ids, *repo[1].evidence_ids])),
        })
        by_identity[key] = (package[0], merged)
        skipped.append(repo[0].name)
    return list(by_identity.values()), skipped


def core_rounds(board) -> int:
    """Scouting rounds of CORE capabilities: what a review must have seen to be current."""
    core = {c.id for c in board.capabilities if c.priority == "core"}
    return sum(n for cid, n in board.scout_rounds.items() if cid in core)


def component_id(capability_id: str, source: str, reference: str) -> str:
    return "cmp-" + hashlib.sha1(f"{capability_id}|{source}|{reference.lower()}".encode()).hexdigest()[:10]


async def submit_components(args: SubmitComponentsArgs, ctx: ToolContext) -> ToolResult:
    capability_id = ctx.assignment.get("capability_id")
    if len(args.components) > MAX_COMPONENTS:
        return refuse(f"propose at most {MAX_COMPONENTS} components; keep the best-checked ones")
    # Unverified items are DROPPED, never accepted. The verified ones are kept,
    # so a scout reporting on its last turn does not lose all its work over
    # one name it never checked. If nothing is verified, the report is refused.
    verified, problems = [], []
    for item in args.components:
        facts = ctx.known(item.source, item.reference.strip())
        if facts is None:
            problems.append(f"{item.reference}: not looked at in this run; search, inspect or look it up first")
        elif item.source == "github" and not facts.inspected:
            problems.append(f"{item.reference}: only seen in a search; inspect_repository it first")
        else:
            verified.append((item, facts))
    if problems and not verified:
        return refuse("; ".join(problems))
    # LEARNING NOTE: tell the scout once, instead of silently dropping (found live)
    #   Scouts named the main project of an approach (an identity server, a
    #   speech engine) without inspecting it, and it was dropped with only a
    #   note, so its wrappers were listed and the thing itself was missing.
    #   The first time, the report is sent back with the list, so the scout can
    #   inspect them or take them out. The second time, unverified ones are
    #   dropped as before, so a stubborn model still finishes.
    if problems and not ctx.assignment.get("unverified_refused"):
        ctx.assignment["unverified_refused"] = True
        return refuse(
            "not yet proposable: " + "; ".join(problems) +
            ". Inspect or look up each one first (inspect_repository, lookup_npm, lookup_pypi), "
            "or leave it out, then submit again."
        )
    if not args.summary.strip():
        return refuse("add a short summary for the team lead")
    for problem in problems:
        ctx.notes.append(f"Not proposed (unverified): {problem.split(':')[0]}")

    capability = next((c for c in ctx.board.capabilities if c.id == capability_id), None)
    listed = capability.approaches if capability else []
    unmatched = [i.name for i, _ in verified if listed and resolve_approach(i.approach, listed) is None]
    if unmatched:
        options = "; ".join(f"A{n}: {a}" for n, a in enumerate(listed, 1))
        return refuse(f"{', '.join(unmatched)}: say which listed approach it represents ({options})")

    already = {identity(c.facts) for c in ctx.board.components if c.capability_id == capability_id}
    verified, duplicates = merge_duplicates(verified, already)

    components = []
    seen = set()
    for item, facts in verified:
        cid = component_id(capability_id, item.source, facts.reference)
        if cid in seen:
            continue
        seen.add(cid)
        for eid in facts.evidence_ids:
            if eid in ctx.pending:
                ctx.publish(ctx.pending[eid])
        components.append(ComponentCandidate(
            id=cid, capability_id=capability_id, name=item.name.strip()[:80],
            approach=resolve_approach(item.approach, listed) or (item.approach or "").strip()[:APPROACH_LABEL_LENGTH] or None, provides=item.provides.strip()[:400],
            fit_notes=item.fit_notes.strip()[:500], concerns=[c.strip()[:200] for c in item.concerns if c.strip()][:5],
            facts=facts, proposed_by="component_scout",
        ))
    ctx.outcome = {"components": [c.model_dump(mode="json") for c in components], "summary": args.summary.strip()[:600]}
    return reply({"accepted": len(components), "dropped_unverified": problems,
                  "merged_or_already_listed": list(dict.fromkeys(duplicates))}, terminal=True)


# --- submit_projects -----------------------------------------------------------------
class ProjectIn(BaseModel):
    reference: str = Field(description='The GitHub repository as "owner/name".')
    why_similar: str
    worth_learning: str = Field(description="What the project could teach or lend to this one.")


class SubmitProjectsArgs(BaseModel):
    projects: list[ProjectIn]
    summary: str


async def submit_projects(args: SubmitProjectsArgs, ctx: ToolContext) -> ToolResult:
    if len(args.projects) > MAX_PROJECTS:
        return refuse(f"propose at most {MAX_PROJECTS} projects")
    missing = [p.reference for p in args.projects if ctx.known("github", p.reference.strip()) is None]
    if missing:
        return refuse(f"not seen in a search in this run: {', '.join(missing)}")
    projects = []
    for item in args.projects:
        facts = ctx.known("github", item.reference.strip())
        for eid in facts.evidence_ids:
            if eid in ctx.pending:
                ctx.publish(ctx.pending[eid])
        projects.append(SimilarProject(name=facts.reference, why_similar=item.why_similar.strip()[:300],
                                       worth_learning=item.worth_learning.strip()[:300], facts=facts))
    ctx.outcome = {"projects": [p.model_dump(mode="json") for p in projects], "summary": args.summary.strip()[:600]}
    return reply({"accepted": len(projects)}, terminal=True)


# --- submit_review -------------------------------------------------------------------
class GapIn(BaseModel):
    capability_id: str
    missing: str


class SubmitReviewArgs(BaseModel):
    complete: bool
    gaps: list[GapIn] = Field(default_factory=list)
    notes: str = ""


async def submit_review(args: SubmitReviewArgs, ctx: ToolContext) -> ToolResult:
    known = {c.id for c in ctx.board.capabilities}
    unknown = [g.capability_id for g in args.gaps if g.capability_id not in known]
    if unknown:
        return refuse(f"these capability ids do not exist: {', '.join(unknown)}")
    gaps = [ReviewGap(capability_id=g.capability_id, missing=g.missing.strip()[:600]) for g in args.gaps if g.missing.strip()]
    # Found live: a reviewer declared coverage complete while a core stage had
    # nothing usable. Code checks the one thing it can: every core capability
    # needs at least one building block (judged fit 2 or 3, or not yet judged).
    covered = {c.capability_id for c in ctx.board.components if c.fit is None or c.fit >= 2}
    for cap in ctx.board.capabilities:
        if cap.priority == "core" and cap.id not in covered and not any(g.capability_id == cap.id for g in gaps):
            gaps.append(ReviewGap(capability_id=cap.id, missing=f"no usable building block yet for the core stage '{cap.name}'"))
    verdict = ReviewVerdict(complete=args.complete and not gaps, gaps=gaps, notes=args.notes.strip()[:600],
                            scouting_seen=core_rounds(ctx.board))
    ctx.outcome = {"review": verdict.model_dump(mode="json")}
    return reply({"recorded": True, "complete": verdict.complete}, terminal=True)


# --- submit_fit ----------------------------------------------------------------------
class FitIn(BaseModel):
    id: str = Field(description="The candidate's id, exactly as given.")
    fit: int = Field(ge=0, le=3, description="3 direct fit, 2 partial fit, 1 reference only, 0 unrelated.")
    kind: Literal["building_block", "framework", "service", "reference_app"]
    reason: str = Field(description="One short sentence pointing at what in the retrieved text shows the fit.")
    approach: int | None = Field(default=None, ge=0, description="The number of the listed approach it really "
                                 "represents (1 for A1, ...), or 0 if it represents none of them.")


class SubmitFitArgs(BaseModel):
    assessments: list[FitIn]


async def submit_fit(args: SubmitFitArgs, ctx: ToolContext) -> ToolResult:
    expected = set(ctx.assignment.get("component_ids", []))
    given = [a.id for a in args.assessments]
    unknown = [i for i in given if i not in expected]
    if unknown:
        return refuse(f"these ids are not candidates: {', '.join(unknown)}")
    missing = sorted(expected - set(given))
    if missing:
        return refuse(f"assess every candidate; missing: {', '.join(missing)}")
    # A finished application is a reference by definition. Found live: the judge
    # called demos "direct fit" while labelling them finished apps; code settles it.
    ctx.outcome = {"assessments": {
        a.id: {"fit": min(a.fit, 1) if a.kind == "reference_app" else a.fit, "kind": a.kind, "reason": a.reason.strip()[:200],
               "approach": a.approach}
        for a in args.assessments
    }}
    return reply({"assessed": len(args.assessments)}, terminal=True)


RECORD_CAPABILITIES = Tool(
    name="record_capabilities",
    description="Record the technical capabilities the project needs, each with the approaches worth comparing. Ends your work.",
    args=RecordCapabilitiesArgs, run=record_capabilities, terminal=True,
)
SUBMIT_COMPONENTS = Tool(
    name="submit_components",
    description="Hand in the open-source components you found for your capability (may be empty, with an honest summary). Ends your work.",
    args=SubmitComponentsArgs, run=submit_components, terminal=True,
)
SUBMIT_PROJECTS = Tool(
    name="submit_projects",
    description="Hand in whole projects similar to the idea. Ends your work.",
    args=SubmitProjectsArgs, run=submit_projects, terminal=True,
)
SUBMIT_REVIEW = Tool(
    name="submit_review",
    description="Hand in your review of the research coverage. Ends your work.",
    args=SubmitReviewArgs, run=submit_review, terminal=True,
)
SUBMIT_FIT = Tool(
    name="submit_fit",
    description="Hand in your relevance assessment of every candidate. Ends your work.",
    args=SubmitFitArgs, run=submit_fit, terminal=True,
)
