"""
Suggestions: ideas the model offers for completing a brief.

What this file does
    Two groups of shapes:

      Draft...      what the MODEL returns. Untrusted, strict (every field
                    required), like BriefDraft in brief_draft.py.
      Brief...      what Archway SENDS to the UI after plain Python has
                    cleaned the model's reply (app/briefing/suggestions.py).

Why suggestions are separate from the brief
    A suggestion is the model's idea, not something the user said or
    decided. It becomes part of the brief ONLY when the user chooses it, and
    then it is the user's decision. Until then it is never stored in a brief.

How it plugs in
    app/workflow/suggestions_service.py creates them; app/api/suggestions.py
    returns them; the UI shows them with an "AI suggestion" label.
"""

from typing import Literal

from app.models.brief_draft import StrictModel
from app.models.common import ArchwayModel, ServiceMode

# Where an accepted answer to an "unknown" is added.
AddAs = Literal["must_have", "assumption"]
ConstraintField = Literal["budget", "privacy", "deployment", "stated"]


# --- What the model returns (strict) ---------------------------------------------
class DraftSuggestion(StrictModel):
    text: str
    reason: str


class DraftConstraintSuggestion(StrictModel):
    field: ConstraintField
    text: str
    reason: str


class DraftAnswer(StrictModel):
    text: str
    reason: str
    add_as: AddAs


class DraftUnknownAnswers(StrictModel):
    unknown: str  # the exact text of one of the brief's unknowns
    answers: list[DraftAnswer]


class SuggestionsDraft(StrictModel):
    must_have: list[DraftSuggestion]
    nice_to_have: list[DraftSuggestion]
    stack: list[DraftSuggestion]
    constraints: list[DraftConstraintSuggestion]
    assumptions: list[DraftSuggestion]
    unknowns: list[DraftUnknownAnswers]


# --- What Archway sends to the UI --------------------------------------------------
class Suggestion(ArchwayModel):
    text: str
    reason: str | None = None


class ConstraintSuggestion(Suggestion):
    field: ConstraintField


class AnswerSuggestion(Suggestion):
    add_as: AddAs
    # True for a fixed, generic option added by code because the model gave no
    # answer for this question. The UI labels it so it is never mistaken for
    # something the model wrote about this project.
    standard: bool = False


class UnknownAnswers(ArchwayModel):
    unknown: str
    answers: list[AnswerSuggestion]


# Bump when a block is added, so suggestions saved by an older version are
# written again instead of showing empty panels.
SUGGESTIONS_SCHEMA = 2


class BriefSuggestions(ArchwayModel):
    brief_version: int  # the brief version these suggestions were written for
    schema_version: int = 1  # saved rows from before this field existed read as 1
    must_have: list[Suggestion]
    nice_to_have: list[Suggestion] = []
    stack: list[Suggestion] = []
    constraints: list[ConstraintSuggestion]
    assumptions: list[Suggestion]
    unknowns: list[UnknownAnswers]
    # Who wrote them, so the UI can say so honestly.
    mode: ServiceMode
    model: str | None = None
