"""
The build plan (Phase 6): a roadmap of tasks, the decisions behind it, and a pack of staged coding prompts.

What this file does
    Defines what the plan stage produces, from the approved architecture version:

        Task             one piece of work, with its prerequisites, scope, acceptance criteria and checks
        Decision         an Architecture Decision Record (ADR): what was chosen, and what was rejected and why
        Roadmap          the tasks in dependency order, and the decisions
        PromptFile       one file of the prompt pack (a staged prompt, or a context file)
        RubricCheck      one line of the prompt quality rubric (IMPLEMENTATION_GUIDE.md 8.5), passed or not
        PlanLink         one source-to-decision link: requirement -> task -> component -> verdict -> evidence
        PlanSnapshot     everything the Plan step shows

Rules built in
    - A plan records WHICH option version it was built for. When a newer version is approved, the plan is stale
      (the snapshot says so); it is never silently reused for a different architecture.
    - A rubric line that did not pass is kept and shown. A plan whose checks still fail after the retry is
      exported as PARTIAL, never presented as passing.

How it plugs in
    app/roadmap/ builds the roadmap, app/promptgen/ writes and checks the prompts, the graph nodes in
    app/graph/nodes/ (build_roadmap, generate_prompts, check_prompts, export) run them, and app/db/plans_repo.py
    saves the result.
"""

from typing import Literal

from pydantic import Field

from app.models.common import ArchwayModel
from app.models.option_flow import VersionRef

# The default prompt stages (IMPLEMENTATION_GUIDE.md 8.2), in the order they are built.
Stage = Literal["scaffold", "data_and_storage", "backend_features", "integrations", "frontend", "tests_and_security"]
STAGES: tuple[str, ...] = ("scaffold", "data_and_storage", "backend_features", "integrations", "frontend", "tests_and_security")
STAGE_TITLES = {
    "scaffold": "Scaffold", "data_and_storage": "Data and storage", "backend_features": "Backend features",
    "integrations": "Integrations", "frontend": "Frontend", "tests_and_security": "Tests and security",
}


class Task(ArchwayModel):
    id: str = Field(min_length=1)  # "T-01", in build order
    title: str = Field(min_length=1)
    goal: str = Field(min_length=1)
    stage: Stage
    # A spike is a small experiment that settles an uncertain integration before the work that depends on it.
    kind: Literal["build", "spike"] = "build"
    prerequisites: list[str] = Field(default_factory=list)  # task ids
    scope: str = Field(min_length=1)
    out_of_scope: list[str] = Field(default_factory=list)
    likely_files: list[str] = Field(default_factory=list)
    interfaces_to_preserve: list[str] = Field(default_factory=list)
    requirement_ids: list[str] = Field(default_factory=list)
    components: list[str] = Field(default_factory=list)  # names of the option's components this task touches
    evidence_ids: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    validation_steps: list[str] = Field(default_factory=list)  # tests or commands to run
    risks: list[str] = Field(default_factory=list)
    validates: list[str] = Field(default_factory=list)  # for a spike: the option's validation tasks it settles


class RejectedAlternative(ArchwayModel):
    option: str = Field(min_length=1)
    why: str = Field(min_length=1)


class Decision(ArchwayModel):
    id: str = Field(min_length=1)  # "ADR-1"
    title: str = Field(min_length=1)
    context: str = Field(min_length=1)
    decision: str = Field(min_length=1)
    rejected: list[RejectedAlternative] = Field(default_factory=list)
    consequences: str | None = None
    source: Literal["options", "model"]  # written by code from the compared options, or by the planning model


class Roadmap(ArchwayModel):
    architecture: VersionRef  # the approved option version this roadmap is for
    brief_version: int = Field(ge=1)
    tasks: list[Task] = Field(default_factory=list)  # in build order: every prerequisite comes first
    decisions: list[Decision] = Field(default_factory=list)


class RubricCheck(ArchwayModel):
    criterion: str = Field(min_length=1)  # e.g. "Maps to a roadmap task"
    passed: bool
    detail: str | None = None  # why it failed, in a few words


class PromptFile(ArchwayModel):
    path: str = Field(min_length=1)  # inside build-pack/, e.g. "prompts/01_scaffold.md"
    title: str = Field(min_length=1)
    kind: Literal["prompt", "context", "checklist"]
    content: str = Field(min_length=1)
    task_ids: list[str] = Field(default_factory=list)  # prompts only
    prerequisites: list[str] = Field(default_factory=list)  # paths of earlier prompts (prompts only)
    rubric: list[RubricCheck] = Field(default_factory=list)  # prompts only


class PlanLink(ArchwayModel):
    """One requirement traced to the work and the evidence behind it (Checkpoint 6: source-to-decision links)."""

    requirement_id: str
    requirement: str
    coverage: str  # how the approved option covers it
    task_ids: list[str] = Field(default_factory=list)
    components: list[dict] = Field(default_factory=list)  # name, kind, repo, eligibility, decided_by, receipt ids, evidence


class PlanSnapshot(ArchwayModel):
    """The saved picture of a run's build plan. Empty until the plan has been asked for."""

    requested: bool = False
    built_for: VersionRef | None = None  # the option version the plan was built from
    approved: VersionRef | None = None  # the version approved NOW
    stale: bool = False  # built for a version that is no longer the approved one
    roadmap: Roadmap | None = None
    files: list[PromptFile] = Field(default_factory=list)
    links: list[PlanLink] = Field(default_factory=list)
    passed: bool | None = None  # every rubric line of every prompt passed (None until checked)
    outcome: Literal["full", "partial"] | None = None  # partial: some checks still fail after the retry
    notes: list[str] = Field(default_factory=list)
    completed: list[str] = Field(default_factory=list)  # prompt paths the person marked as done
