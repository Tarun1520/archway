"""
Shapes used by the research team (Phase 3, agentic).

    Candidate          one repository a GitHub search returned (a raw search hit)
    SourceFacts        the FACTS about one source (repo or package), filled by code
    Capability         one technical capability the idea needs, and the
                       different approaches worth comparing for it
    ComponentCandidate one open-source building block an agent proposes for a
                       capability: the agent's claims PLUS the code's facts
    SimilarProject     a whole project like the idea (secondary research)
    ReviewVerdict      the reviewer agent's judgement of coverage
    TeamMessage        one message agents send each other (tasks and reports)
    ResearchSnapshot   everything the Research tab shows

The line between claims and facts
    What an agent WRITES ("it parses PDF tables well") is a claim, kept in
    `provides` / `fit_notes`, and must cite evidence ids. What is FACT
    (license, archived, stars, last activity) is copied by code from the
    evidence the tools retrieved. An agent cannot set or change a fact.
"""

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.models.common import ArchwayModel, ServiceMode
from app.models.evidence import EvidenceItem, RepoEvidence

AgentName = Literal["research_lead", "capability_analyst", "component_scout", "project_scout", "reviewer", "relevance_judge"]
LicenseStatus = Literal["detected", "unrecognised", "none_detected", "not_retrieved"]
SourceKind = Literal["github", "pypi", "npm"]


class Candidate(ArchwayModel):
    """A repository that a search returned. Nothing has been inspected yet."""

    repo: str = Field(min_length=1)  # "owner/name"
    url: str = Field(min_length=1)
    description: str | None = None
    language: str | None = None
    topics: list[str] | None = None
    license: str | None = None  # what GitHub's search reported; None = none detected
    archived: bool | None = None
    last_push: datetime | None = None
    stars: int | None = Field(default=None, ge=0)
    homepage: str | None = None
    found_by: list[int] = Field(default_factory=list)
    retrieved_at: datetime
    from_cache: bool = False
    mode: ServiceMode = "live"


class SourceFacts(ArchwayModel):
    """What the tools established about one source. Written only by code."""

    kind: SourceKind
    reference: str  # "owner/name" for GitHub, the package name otherwise
    url: str
    description: str | None = None
    license: str | None = None
    license_status: LicenseStatus = "not_retrieved"
    archived: bool | None = None
    stars: int | None = None
    downloads_last_month: int | None = None  # registries only; None = not known
    source_repo: str | None = None  # registries only: the GitHub "owner/name" the package says it lives in
    last_activity: datetime | None = None  # last push (GitHub) or last release (registries)
    inspected: bool = False  # True once README/license (or registry details) were read
    evidence_ids: list[str] = Field(default_factory=list)
    mode: ServiceMode = "live"


class Capability(ArchwayModel):
    id: str = Field(min_length=1)  # "CAP-1"
    name: str = Field(min_length=1)  # e.g. "Document parsing"
    need: str  # what the product needs it for, in the brief's terms
    requirement_ids: list[str] = Field(default_factory=list)
    # The different ways this capability can be built, to be compared.
    approaches: list[str] = Field(default_factory=list)
    search_hints: list[str] = Field(default_factory=list)
    # "core": a stage of the product's central job, without which it does not exist
    # (researched first and deepest). "supporting": what helps around it
    # (accounts, storage, notifications ...), researched after, more lightly.
    priority: Literal["core", "supporting"] = "core"


class ComponentCandidate(ArchwayModel):
    id: str = Field(min_length=1)  # "CMP-1", assigned by code
    capability_id: str
    name: str
    approach: str | None = None  # which of the capability's approaches it represents
    # --- Claims: written by an agent, each resting on evidence -------------------
    provides: str  # what it gives the project
    fit_notes: str  # why it might fit this brief
    concerns: list[str] = Field(default_factory=list)
    # --- Facts: copied by code from the evidence ---------------------------------
    facts: SourceFacts
    proposed_by: AgentName = "component_scout"
    # --- Relevance: written by the blind relevance judge, which never sees the
    # scout's claims above, only the retrieved facts (None = not assessed). -----
    fit: int | None = Field(default=None, ge=0, le=3)  # 3 direct, 2 partial, 1 reference only, 0 unrelated
    kind: Literal["building_block", "framework", "service", "reference_app"] | None = None
    fit_reason: str | None = None


class SimilarProject(ArchwayModel):
    name: str
    why_similar: str
    worth_learning: str  # what could be borrowed or learned from it
    facts: SourceFacts


class ReviewGap(ArchwayModel):
    capability_id: str
    missing: str  # what is missing, e.g. "no option for the hosted approach"


class ReviewVerdict(ArchwayModel):
    complete: bool
    gaps: list[ReviewGap] = Field(default_factory=list)
    notes: str = ""
    # How many scouting jobs had finished when this review was written. A
    # review is "fresh" only while no scouting has happened since.
    scouting_seen: int = 0


class TeamMessage(ArchwayModel):
    """One message on the team channel. This is how the agents talk to each other."""

    id: str
    sender: AgentName
    recipient: AgentName | Literal["team"]
    kind: Literal["task", "report", "review", "note"]
    content: str
    capability_ids: list[str] = Field(default_factory=list)
    created_at: datetime


class SourceUse(ArchwayModel):
    """One outside source a run looked in, and how much it used it. Totalled from the run's saved events."""

    source: str  # "github" | "npm" | "pypi" | "hacker_news" | "stack_overflow" | "brave"
    lookups: int  # how many times a tool asked it something
    results: int  # how many things it gave back, in all


class ResearchSnapshot(ArchwayModel):
    """The saved picture of a run's research, for the Research tab."""

    capabilities: list[Capability] = Field(default_factory=list)
    components: list[ComponentCandidate] = Field(default_factory=list)
    projects: list[SimilarProject] = Field(default_factory=list)
    review: ReviewVerdict | None = None
    messages: list[TeamMessage] = Field(default_factory=list)
    repos: list[RepoEvidence] = Field(default_factory=list)  # inspected GitHub repositories
    evidence: list[EvidenceItem] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    # Phase 4: one verdict per component (EligibilityResult + component_id), one receipt per question.
    eligibility: list[dict] = Field(default_factory=list)
    receipts: list[dict] = Field(default_factory=list)
    sources: list[SourceUse] = Field(default_factory=list)  # where this run looked (empty for runs from before this was recorded)
    finished: bool = False
    mode: ServiceMode = "live"
