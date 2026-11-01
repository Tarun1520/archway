"""
ArchitectureOption: one proposed way to build the project.

What this file does
    Defines an option and its parts. Each component is tagged `reuse` (take
    an open-source repository) or `build` (write it yourself).

Rules built in
    - A `reuse` component must name the repository it reuses.
    - An option records the brief VERSION it was drafted from, so a later
      brief edit cannot silently be treated as covered.
    - Claims we could not support become `validation_tasks`, not assertions.

How it plugs in
    Phase 5's `draft_options` node creates one to three of these (code builds
    them from the model's draft: app/options/draft.py); `review_options`
    attaches an OptionReview; `approve_version` sets `approved` on one specific
    version. A revision never edits a version: it makes the next one.
"""

from typing import Literal

from pydantic import Field, model_validator

from app.models.common import ArchwayModel

Coverage = Literal["covered", "partial", "not_covered", "unknown"]

# The eight ways options are compared (IMPLEMENTATION_GUIDE.md 7.2). Qualitative on purpose:
# no invented hours or savings.
Dimension = Literal[
    "simplicity", "effort", "oss_reuse", "integration_risk", "maintainability", "privacy", "cost_exposure", "evidence_coverage"
]
DIMENSIONS: tuple[str, ...] = (
    "simplicity", "effort", "oss_reuse", "integration_risk", "maintainability", "privacy", "cost_exposure", "evidence_coverage"
)
# "good" is always the favourable end (simple, light, private, cheap, well supported), whatever the dimension.
Rating = Literal["good", "mixed", "poor", "unknown"]


class DimensionNote(ArchwayModel):
    dimension: Dimension
    rating: Rating
    note: str = Field(min_length=1)


class ReviewIssue(ArchwayModel):
    severity: Literal["blocking", "warning"]
    kind: str = Field(min_length=1)  # e.g. "reuse_not_eligible", "constraint", "unsupported_claim"
    text: str = Field(min_length=1)
    source: Literal["rules", "model"]  # plain code found it, or the reviewing model did


class OptionReview(ArchwayModel):
    """The review gate's verdict on ONE option version (IMPLEMENTATION_GUIDE.md 7.3)."""

    passed: bool
    issues: list[ReviewIssue] = Field(default_factory=list)
    llm_checked: bool  # False when the model check could not run (cap reached, service down): said, never hidden


class Component(ArchwayModel):
    name: str = Field(min_length=1)
    responsibility: str = Field(min_length=1)
    kind: Literal["reuse", "build"]
    repo: str | None = None  # required when kind == "reuse"
    # The researched component this reuses (its id, e.g. "CMP-3"), so its eligibility and
    # decision receipts can be shown beside it. Set by code, never by the model's say-so.
    candidate_id: str | None = None

    @model_validator(mode="after")
    def reuse_names_its_repository(self):
        if self.kind == "reuse" and not self.repo:
            raise ValueError("a 'reuse' component must name the repository it reuses")
        if self.kind == "build" and self.repo:
            raise ValueError("a 'build' component must not name a repository")
        return self


class ReusedRepo(ArchwayModel):
    repo: str = Field(min_length=1)
    role: str = Field(min_length=1)  # what it does in this architecture


class ArchitectureOption(ArchwayModel):
    id: str = Field(min_length=1)
    version: int = Field(ge=1)  # a revision creates a NEW version
    brief_version: int = Field(ge=1)  # the brief this option was drafted from

    name: str = ""  # a short label, e.g. "Reuse-first"
    trade_off: str | None = None  # the one real difference: what this option trades for what
    summary: str = Field(min_length=1)
    # requirement id -> how well this option covers it.
    requirement_coverage: dict[str, Coverage] = Field(default_factory=dict)
    coverage_notes: dict[str, str] = Field(default_factory=dict)  # requirement id -> why

    components: list[Component] = Field(default_factory=list)
    reused_repos: list[ReusedRepo] = Field(default_factory=list)

    # Free-text sections. None = not written yet (never an invented filler).
    integration_boundaries: str | None = None
    data_flow: str | None = None
    storage_model: str | None = None
    deployment: str | None = None
    security_privacy: str | None = None
    testing_approach: str | None = None

    risks: list[str] = Field(default_factory=list)
    validation_tasks: list[str] = Field(default_factory=list)
    mermaid: str | None = None  # diagram source; rendered safely by the frontend
    evidence_ids: list[str] = Field(default_factory=list)
    pros: list[str] = Field(default_factory=list)
    cons: list[str] = Field(default_factory=list)
    choose_if: str | None = None  # the situation in which this is the right pick
    avoid_if: str | None = None  # the situation in which it is not
    comparison: list[DimensionNote] = Field(default_factory=list)
    # Set on a revision: what changed from the previous version, and what else it touches.
    change_summary: str | None = None
    review: OptionReview | None = None

    # True only after the user approves THIS version.
    approved: bool = False

    @model_validator(mode="after")
    def reused_repos_match_reuse_components(self):
        """Every repository a component reuses must be listed with its role."""
        listed = {item.repo for item in self.reused_repos}
        used = {component.repo for component in self.components if component.kind == "reuse"}
        not_listed = sorted(used - listed)
        if not_listed:
            raise ValueError(f"components reuse repositories missing from reused_repos: {not_listed}")
        return self
