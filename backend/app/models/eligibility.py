"""
EligibilityResult: the verdict of the deterministic eligibility gate.

What this file does
    Records whether a repository MAY be recommended for reuse, and why not
    when it may not. The gate itself (plain Python rules, no model) is built
    in Phase 4 in app/policy/. This file is only the shape of its answer.

The invariant
    No model judgment may override an exclusion. A high suitability score
    never compensates for a status other than "eligible".

Learn more: LEARNING_GUIDE.md topic 38, backend/learning/22_policy_gate.py
"""

from typing import Literal

from pydantic import Field, model_validator

from app.models.common import ArchwayModel

EligibilityStatus = Literal["eligible", "review_required", "excluded", "unresolved"]


class EligibilityResult(ArchwayModel):
    repo: str = Field(min_length=1)
    status: EligibilityStatus
    reasons: list[str] = Field(default_factory=list)
    # What decided it: the plain rules, or (only for "the evidence does not show it meets the requirement")
    # the decision model's answer, which the studio then labels with the engine's name (e.g. Laya).
    decided_by: Literal["rules", "decision_model"] = "rules"
    # Which version of the rules produced this verdict, so an old result can
    # be understood after the policy changes.
    policy_version: str = Field(min_length=1)

    @model_validator(mode="after")
    def anything_but_eligible_must_say_why(self):
        if self.status != "eligible" and not self.reasons:
            raise ValueError(f"status '{self.status}' needs at least one reason")
        return self
