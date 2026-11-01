"""
Shapes used while a run is in progress: questions, answers, edits, snapshots.

    ClarifyQuestion   one question Archway asks the user
    ClarifyAnswer     the user's reply to the clarify step
    BriefEdit         the user's edited version of the brief
    ConfirmDecision   approve the brief, or submit an edit
    WaitingFor        which step is paused, and what it is asking
    UsageCount        calls made so far for one service, with its cap
    RunSnapshot       everything the UI needs to redraw a run from scratch
    RunEvent          one saved progress event

How it plugs in
    app/api/workflow.py receives ClarifyAnswer / ConfirmDecision and returns
    RunSnapshot. The graph nodes in app/graph/nodes/ produce ClarifyQuestion
    and consume the answers.
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from app.models.brief import Assumption, Constraints, ProjectBrief, Requirement
from app.models.common import ArchwayModel
from app.models.run import Run

# "idea" is a special topic: it asks what the person wants to build, and only
# appears when their message did not describe a project at all.
Topic = Literal["idea", "meaning", "material", "deployment", "users", "sensitive_data", "budget", "integrations"]


class ClarifyQuestion(ArchwayModel):
    topic: Topic
    question: str
    why: str | None = None  # shown to the user as "Why we ask"


class ClarifyAnswer(ArchwayModel):
    """The user's reply at the clarify step.

    `answers` maps a topic to the user's text. A topic left out, or left
    blank, was not answered. With `continue_with_assumptions` every
    unanswered topic becomes a visible assumption instead.
    """

    answers: dict[Topic, str] = Field(default_factory=dict)
    continue_with_assumptions: bool = False


class EditedItem(ArchwayModel):
    """A requirement or assumption as edited by the user.

    Keep `id` to say "this is the same item, reworded". Leave it out for a
    brand-new item; Archway then gives it a new id.
    """

    id: str | None = None
    text: str = Field(min_length=1)


class BriefEdit(ArchwayModel):
    problem: str = Field(min_length=1)
    users: str | None = None
    must_have: list[EditedItem] = Field(default_factory=list)
    nice_to_have: list[EditedItem] = Field(default_factory=list)
    stack_preferences: list[str] = Field(default_factory=list)
    constraints: Constraints = Field(default_factory=Constraints)
    assumptions: list[EditedItem] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)


class ConfirmDecision(ArchwayModel):
    """The user's reply at the confirm step: approve as shown, or send an edit."""

    action: Literal["approve", "edit"]
    edit: BriefEdit | None = None  # required when action == "edit"


class WaitingFor(ArchwayModel):
    node: Literal["clarify", "confirm_brief", "select_or_revise", "approve_version"]
    # What the paused step is asking. For clarify: {"questions": [...]}.
    payload: dict[str, Any]


class UsageCount(ArchwayModel):
    service: Literal["llm", "jev", "github"]
    calls: int
    cap: int | None  # None = this service has no per-run cap


class AskedQuestion(ArchwayModel):
    """A question the run asked, and the user's answer (None = skipped, so assumed)."""

    topic: str
    question: str
    answer: str | None = None


class RunSnapshot(ArchwayModel):
    run: Run
    waiting_for: WaitingFor | None  # None = not paused for the user
    finished: bool  # True when the workflow has nothing left to do
    running: bool = False  # True while the workflow is working (e.g. the research team)
    brief: ProjectBrief | None  # the newest version, if any
    brief_versions: list[int]
    usage: list[UsageCount]
    last_event_id: int  # so the UI can ask for only newer events
    asked_questions: list[AskedQuestion] = []  # for showing the questions step again


class RunEvent(ArchwayModel):
    id: int
    run_id: str
    name: str
    data: dict[str, Any]
    created_at: datetime


# Re-exported so other files can import these two from one place.
__all__ = [
    "Assumption", "BriefEdit", "ClarifyAnswer", "ClarifyQuestion", "ConfirmDecision", "EditedItem",
    "Requirement", "RunEvent", "RunSnapshot", "Topic", "UsageCount", "WaitingFor",
]
