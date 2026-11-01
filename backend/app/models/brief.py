"""
ProjectBrief: the structured version of the user's idea.

What this file does
    Defines the brief and its parts. The brief is what the user confirms
    before any research starts, and every later result records which brief
    VERSION it was built from.

Two rules built into these models
    1. What the USER said and what Archway ASSUMED are stored separately
       (`must_have` versus `assumptions`), so the UI can show them apart.
    2. Things we do not know stay unknown: `None`, or listed in `unknowns`.

How it plugs in
    Phase 2's `intake` node will produce a ProjectBrief; `confirm_brief`
    will set `confirmed`. Sample briefs in backend/fixtures/briefs/ use it now.
"""

from pydantic import Field, model_validator

from app.models.common import ArchwayModel


class Requirement(ArchwayModel):
    """One thing the project must (or should) do.

    The `id` is STABLE: it does not change when the text is edited. Evidence
    and decisions point at requirements by id, e.g. "REQ-2".
    """

    id: str = Field(min_length=1)
    text: str = Field(min_length=1)


class Assumption(ArchwayModel):
    """Something Archway assumed because the user did not say.

    Kept apart from requirements so the user can see it and correct it.
    """

    id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    reason: str | None = None  # why this was assumed, if known


class Constraints(ArchwayModel):
    """Hard limits. None means "the user has not told us"."""

    budget: str | None = None
    privacy: str | None = None
    deployment: str | None = None
    # Sentences the USER wrote that read like hard limits, kept word for word.
    # They are found by plain Python (app/policy/stated_constraints.py), not by
    # a model, so a stated constraint cannot be silently dropped or reworded.
    stated: list[str] = Field(default_factory=list)


class Conflict(ArchwayModel):
    """Two or more requirements or constraints that cannot all be true."""

    description: str = Field(min_length=1)
    # Which requirement ids are involved. May be empty when the clash is
    # between constraints rather than numbered requirements.
    requirement_ids: list[str] = Field(default_factory=list)


class ProjectBrief(ArchwayModel):
    id: str = Field(min_length=1)
    version: int = Field(ge=1)  # every edit makes a NEW version: 1, 2, 3 ...

    problem: str = Field(min_length=1)
    users: str | None = None  # who it is for; None = not stated

    must_have: list[Requirement] = Field(default_factory=list)
    nice_to_have: list[Requirement] = Field(default_factory=list)
    stack_preferences: list[str] = Field(default_factory=list)
    constraints: Constraints = Field(default_factory=Constraints)

    assumptions: list[Assumption] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    conflicts: list[Conflict] = Field(default_factory=list)

    # False until the user approves this exact version.
    confirmed: bool = False

    @model_validator(mode="after")
    def ids_are_unique_and_conflicts_point_at_real_requirements(self):
        """LEARNING NOTE: a model_validator checks the object AS A WHOLE.
        Field rules (like min_length) check one value. Rules that compare
        several fields go here.
        """
        requirement_ids = [item.id for item in self.must_have + self.nice_to_have]
        duplicates = {item for item in requirement_ids if requirement_ids.count(item) > 1}
        if duplicates:
            raise ValueError(f"requirement ids must be unique; repeated: {sorted(duplicates)}")

        known = set(requirement_ids)
        for conflict in self.conflicts:
            unknown_ids = [item for item in conflict.requirement_ids if item not in known]
            if unknown_ids:
                raise ValueError(f"conflict refers to unknown requirement ids: {unknown_ids}")
        return self
