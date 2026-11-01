"""
Shapes for the options stage (Phase 5): what the user decides, and what the screen shows.

    OptionDecision      the user's reply at `select_or_revise`: pick one, or ask for a change
    ApprovalDecision    the user's reply at `approve_version`: approve THIS version, or ask for a change
    VersionRef          one option version, named by id and number
    OptionsSnapshot     everything the Options step shows, for a run

How it plugs in
    app/api/options.py receives the two decisions and returns an OptionsSnapshot.
    The graph nodes in app/graph/nodes/ consume the decisions.
"""

from typing import Literal

from pydantic import Field, model_validator

from app.models.common import ArchwayModel
from app.models.option import ArchitectureOption


class VersionRef(ArchwayModel):
    id: str = Field(min_length=1)
    version: int = Field(ge=1)


class OptionDecision(ArchwayModel):
    """At `select_or_revise`. `select` needs an option id; `revise` needs a request (and may name an option)."""

    action: Literal["select", "revise"]
    option_id: str | None = None
    request: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def says_enough(self):
        if self.action == "select" and not self.option_id:
            raise ValueError("choosing an option needs its id")
        if self.action == "revise" and not (self.request or "").strip():
            raise ValueError("a revision needs a request, for example 'use fewer dependencies'")
        return self


class ApprovalDecision(ArchwayModel):
    """At `approve_version`: approve exactly the version shown, or ask for a change."""

    action: Literal["approve", "change"]
    request: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def change_needs_a_request(self):
        if self.action == "change" and not (self.request or "").strip():
            raise ValueError("a change needs a request, for example 'use fewer dependencies'")
        return self


class OptionsSnapshot(ArchwayModel):
    """The saved picture of a run's options. Empty until the options step has been asked for."""

    requested: bool = False  # the user asked for options (the graph is, or was, working on them)
    options: list[ArchitectureOption] = Field(default_factory=list)  # every version, oldest first
    presented: list[VersionRef] = Field(default_factory=list)  # the latest versions that passed review
    selected: VersionRef | None = None
    approved: VersionRef | None = None
    notes: list[str] = Field(default_factory=list)  # visible explanations: what failed, what was not checked
    # True when drafting finished with nothing that passed review: "no recommendation, here is what is missing".
    no_recommendation: bool = False
