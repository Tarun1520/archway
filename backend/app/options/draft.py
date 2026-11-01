"""
Drafting options: the shape the model fills in, and the code that turns it into real options.

BEHAVIOUR THIS FILE ENFORCES (the model proposes, code decides)
    - Every field of the draft is required (null where nothing applies), so a strict provider accepts it.
    - A component may be `reuse` only by naming a reusable component's id. The repository name is then COPIED
      from that component's facts. A reuse that names nothing real is dropped and reported as a blocking
      issue, so the review gate sends the option back.
    - Evidence ids are kept only if they exist. Requirement ids only if they are in the brief.
    - Every must-have gets a coverage entry; one the model left out is "unknown", never "covered".
    - The eight comparison dimensions are always present; one not assessed is "unknown".
    - A diagram is kept only if it is safe to draw (mermaid_safe.py).
    - Ids and versions are made here: new options are OPT-1, OPT-2 ...; a revision, or a redraft after a failed
      review, saves the NEXT version of the same option (nothing is edited in place).
"""

from typing import Any, Literal

from app.models.brief_draft import StrictModel
from app.models.option import DIMENSIONS, ArchitectureOption, Component, Dimension, DimensionNote, Rating, ReusedRepo
from app.options.material import reusable_components
from app.options.mermaid_safe import check_mermaid
from app.options.versions import find, next_option_number

MAX_OPTIONS = 3


class DraftCoverage(StrictModel):
    requirement_id: str
    coverage: Literal["covered", "partial", "not_covered", "unknown"]
    note: str


class DraftComponent(StrictModel):
    name: str
    responsibility: str
    kind: Literal["reuse", "build"]
    candidate_id: str | None  # the reusable component's id; null for `build`


class DraftDimension(StrictModel):
    dimension: Dimension
    rating: Rating
    note: str


class DraftOption(StrictModel):
    # A NEW option: any short label ("A", "B"). A REVISION or a fix: the id of the option being changed.
    key: str
    name: str
    trade_off: str
    summary: str
    coverage: list[DraftCoverage]
    components: list[DraftComponent]
    integration_boundaries: str
    data_flow: str
    storage_model: str
    deployment: str
    security_privacy: str
    testing_approach: str
    risks: list[str]
    validation_tasks: list[str]
    mermaid: str | None
    evidence_ids: list[str]
    pros: list[str]
    cons: list[str]
    choose_if: str
    avoid_if: str
    comparison: list[DraftDimension]
    # Set only for a revision: what changed from the previous version and what else it touches.
    change_summary: str | None


class OptionsDraft(StrictModel):
    options: list[DraftOption]
    # Set only when no option can honestly be recommended: what is missing.
    no_recommendation_reason: str | None


def parse_draft(data: dict[str, Any]) -> OptionsDraft:
    """Validate the model's reply, tolerating a field that is meant to be null being left out.

    LEARNING NOTE: strict on what is sent, forgiving on what is NOT the model's decision
      The schema sent to the model lists every field as required (some providers insist). A provider that does not
      enforce it sometimes leaves a null field out entirely (seen live: `change_summary`). Leaving out "nothing"
      means null, so it is filled in here. Everything else must be present and of the right kind.
    """
    data = dict(data)
    data.setdefault("no_recommendation_reason", None)
    options = []
    for option in data.get("options") or []:
        option = dict(option)
        for key in ("change_summary", "mermaid"):
            option.setdefault(key, None)
        option["components"] = [{"candidate_id": None, **part} for part in option.get("components") or []]
        options.append(option)
    data["options"] = options
    return OptionsDraft.model_validate(data)


def _text(value: str | None) -> str | None:
    value = (value or "").strip()
    return value or None


def build_options(
    draft: OptionsDraft, state: dict[str, Any], *, mode: Literal["new", "fix", "revise"], keys: list[str],
) -> tuple[list[dict[str, Any]], dict[str, list[str]], list[str]]:
    """Real options from a draft.

    Returns (the NEW option versions as dicts, problems found while building by "id@version", notes to show).
    `keys` are the option ids being redrafted (fix or revise); empty for a new set.
    """
    existing = state.get("options", [])
    reusable = reusable_components(state)
    brief = state.get("brief") or {}
    must = [r["id"] for r in brief.get("must_have", [])]
    known_requirements = set(must) | {r["id"] for r in brief.get("nice_to_have", [])}
    known_evidence = {e["id"] for e in state.get("evidence", [])}
    brief_version = int(brief.get("version") or 1)

    built: list[dict[str, Any]] = []
    problems: dict[str, list[str]] = {}
    notes: list[str] = []
    counter = next_option_number(existing)

    drafts = draft.options[:MAX_OPTIONS]
    if len(draft.options) > MAX_OPTIONS:
        notes.append(f"The model proposed {len(draft.options)} options; only the first {MAX_OPTIONS} were kept.")
    for item in drafts:
        if mode == "new":
            option_id, version = f"OPT-{counter}", 1
            counter += 1
        else:
            if item.key not in keys:
                notes.append(f"The model returned an option '{item.key}' that was not asked for; it was ignored.")
                continue
            previous = find(existing, item.key)
            option_id, version = item.key, (previous["version"] if previous else 0) + 1
        ref = f"{option_id}@{version}"
        issues: list[str] = []

        components: list[Component] = []
        for part in item.components:
            if part.kind == "build":
                components.append(Component(name=part.name, responsibility=part.responsibility, kind="build"))
                continue
            source = reusable.get(part.candidate_id or "")
            if source is None:
                issues.append(
                    f"'{part.name}' is marked reuse but names no reusable component "
                    f"(candidate_id {part.candidate_id!r}); only components listed as reusable may be reused"
                )
                continue
            components.append(Component(
                name=part.name, responsibility=part.responsibility, kind="reuse",
                repo=source["facts"]["reference"], candidate_id=source["id"],
            ))
        reused: dict[str, ReusedRepo] = {}
        for part in components:
            if part.kind == "reuse" and part.repo not in reused:
                reused[part.repo] = ReusedRepo(repo=part.repo, role=part.responsibility)

        coverage = {c.requirement_id: c.coverage for c in item.coverage if c.requirement_id in known_requirements}
        for requirement_id in must:
            coverage.setdefault(requirement_id, "unknown")  # the model left it out: unknown, never "covered"
        coverage_notes = {c.requirement_id: c.note.strip() for c in item.coverage if c.requirement_id in coverage and c.note.strip()}

        by_dimension = {d.dimension: d for d in item.comparison}
        comparison = [
            DimensionNote(dimension=name, rating=by_dimension[name].rating, note=by_dimension[name].note.strip() or "not stated")
            if name in by_dimension else DimensionNote(dimension=name, rating="unknown", note="not assessed")
            for name in DIMENSIONS
        ]

        diagram, refused = check_mermaid(item.mermaid)
        if item.mermaid and not diagram:
            notes.append(f"{option_id}: its diagram was left out because {refused or 'it was empty'}.")

        option = ArchitectureOption(
            id=option_id, version=version, brief_version=brief_version,
            name=item.name.strip() or option_id, trade_off=_text(item.trade_off),
            summary=item.summary.strip() or "(no summary written)",
            requirement_coverage=coverage, coverage_notes=coverage_notes,
            components=components, reused_repos=list(reused.values()),
            integration_boundaries=_text(item.integration_boundaries), data_flow=_text(item.data_flow),
            storage_model=_text(item.storage_model), deployment=_text(item.deployment),
            security_privacy=_text(item.security_privacy), testing_approach=_text(item.testing_approach),
            risks=[r.strip() for r in item.risks if r.strip()],
            validation_tasks=[v.strip() for v in item.validation_tasks if v.strip()],
            mermaid=diagram,
            evidence_ids=[e for e in dict.fromkeys(item.evidence_ids) if e in known_evidence],
            pros=[p.strip() for p in item.pros if p.strip()], cons=[c.strip() for c in item.cons if c.strip()],
            choose_if=_text(item.choose_if), avoid_if=_text(item.avoid_if),
            comparison=comparison, change_summary=_text(item.change_summary) if mode == "revise" else None,
        )
        built.append(option.model_dump(mode="json"))
        if issues:
            problems[ref] = issues
    return built, problems, notes
