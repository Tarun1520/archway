"""
DecisionReceipt: the saved record of ONE judgment asked of Jev.

What this file does
    Keeps, for every question: what was asked, which evidence was shown,
    what came back, and whether the call was live or a fixture. Receipts are
    what let someone later ask "why did the system say that?".

Signals that stay separate (IMPLEMENTATION_GUIDE.md section 6.4)
    `reported_confidence` is how sure the MODEL said it was. It is not
    correctness, so it is stored on its own and never blended into a score.

How it plugs in
    Phase 4's `jev_decisions` node will create one receipt per question.
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from app.models.common import ArchwayModel, ServiceMode

# The only three kinds of question Archway asks Jev.
QuestionType = Literal["requirement_fit", "integration_risk", "needs_human_review"]


class DecisionReceipt(ArchwayModel):
    id: str = Field(min_length=1)
    created_at: datetime

    candidate_id: str = Field(min_length=1)  # which repository
    requirement_id: str | None = None  # set when the question is about one requirement
    question_type: QuestionType
    rubric_version: str = Field(min_length=1)

    evidence_ids: list[str] = Field(default_factory=list)  # EvidenceItem ids shown to Jev

    jev_mode: ServiceMode  # "live" or "fixture": never left out
    jev_model_id: str | None = None  # None when the service did not report one

    # Exactly what the service returned, kept as-is. None when the call did
    # not happen (for example Jev was unreachable).
    returned_judgment: dict[str, Any] | None = None
    reported_confidence: float | None = Field(default=None, ge=0, le=1)

    aggregation_policy: str | None = None  # how answers were combined, if they were
    # The result Archway uses. None means "not evaluated": never a neutral guess.
    final_result: str | None = None
    needs_review: bool
