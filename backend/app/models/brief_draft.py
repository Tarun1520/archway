"""
BriefDraft: exactly what we ask the language model to return.

What this file does
    Defines the JSON shape the model must fill in when it reads the user's
    idea. It is deliberately NOT the same as ProjectBrief:

      BriefDraft    what a MODEL produced. Untrusted. No ids, no versions.
      ProjectBrief  what ARCHWAY stores. Built from a draft by plain Python
                    (app/briefing/builder.py), which adds ids and versions,
                    keeps stated constraints, and checks for conflicts.

Rules that shape this model
    - Every field is required and unknown fields are forbidden. The model
      provider's "strict" structured-output mode needs that. A value the
      model cannot find must be sent as null, never guessed.
    - `X | None` (null) means "the user did not say".

How it plugs in
    app/graph/nodes/intake.py sends this model's JSON schema to the LLM and
    validates the reply with it.

Learn more: LEARNING_GUIDE.md topic 23.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class StrictModel(BaseModel):
    """Base for model-output shapes: unknown fields are an error."""

    model_config = ConfigDict(extra="forbid")


class DraftAssumption(StrictModel):
    text: str
    reason: str | None  # why the model assumed it


class DraftConflict(StrictModel):
    description: str
    # The exact text of the must-have items involved (may be empty).
    requirement_texts: list[str]


class DraftQuestion(StrictModel):
    """One question the model suggests asking, written about THIS project."""

    # "meaning": what a term central to the idea means, when it is not defined and the readings lead to different designs.
    # "material": something the person refers to but did not include (links, files, a document).
    topic: Literal["meaning", "material", "deployment", "users", "sensitive_data", "budget", "integrations"]
    question: str
    # One sentence naming the two designs the answer chooses between. Shown to
    # the user ("Why we ask") and a nudge for the model not to ask idly.
    why_it_matters: str


class BriefDraft(StrictModel):
    # True only when the text describes something to build. A greeting or
    # unrelated text is False, and then `problem` is null and nothing else is
    # filled in. Archway asks what to build instead of guessing.
    describes_project: bool
    problem: str | None
    users: str | None

    must_have: list[str]
    nice_to_have: list[str]
    stack_preferences: list[str]

    budget: str | None
    privacy: str | None
    deployment: str | None

    # The five architecture-changing facts. null = the user did not say.
    multi_user: bool | None
    handles_sensitive_data: bool | None
    mandatory_integrations: list[str] | None

    assumptions: list[DraftAssumption]
    unknowns: list[str]
    conflicts: list[DraftConflict]

    # Questions worth asking about this specific project, only for the five
    # facts above that are null AND would change which architecture fits.
    # Code decides how many are really asked (app/policy/clarification.py).
    clarifying_questions: list[DraftQuestion]
