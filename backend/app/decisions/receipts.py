"""
Turning decision answers into DecisionReceipts: one per question asked.

What a receipt keeps (app/models/receipt.py)
    the question type and requirement, the rubric version, the evidence shown,
    live or fixture, the model id, the answer exactly as returned, the
    model's reported confidence (stored apart: confidence is not correctness),
    the final result Archway uses, and whether a person should review it.

When to flag for review
    a choice or score whose best option has under 60% probability, or a yes/no
    probability between 35% and 65%: the model itself is unsure.

Not evaluated
    When the service was unavailable or the call cap was reached, receipts are
    still written, with no answer and final_result None ("not evaluated"),
    so the gap is visible instead of silently filled.
"""

from typing import Any

from app.decisions.client import DecisionResponse
from app.decisions.questions import FIT_LABELS, RUBRIC_VERSION
from app.models.common import new_id, utc_now
from app.models.receipt import DecisionReceipt

UNSURE_BELOW = 0.6
# The yes/no band where an answer is "unsure". Laya's raw probabilities are not
# calibrated: in the spike its clear "yes" answers sat at 0.52 to 0.67 and its
# clear "no" answers at 0.18 or below, so for it the unsure band is 0.30 to 0.50.
UNSURE_BAND = (0.35, 0.65)
BANDS = {"laya": (0.30, 0.50)}


def _question_type(name: str) -> tuple[str, str | None]:
    if name.startswith("fit__"):
        return "requirement_fit", name.removeprefix("fit__")
    return ("integration_risk" if name == "risk" else "needs_human_review"), None


def _interpret(answer: dict[str, Any], band: tuple[float, float] = UNSURE_BAND) -> tuple[str | None, float | None, bool]:
    """(final result, reported confidence, unsure?) from one answer."""
    kind = answer.get("type")
    if kind == "boolean" and isinstance(answer.get("probability"), (int, float)):
        p = float(answer["probability"])
        threshold = (band[0] + band[1]) / 2 if band != UNSURE_BAND else 0.5
        return ("yes" if p >= threshold else "no"), max(p, 1 - p), band[0] <= p <= band[1]
    probabilities = answer.get("probabilities") or {}
    if kind == "choice" and answer.get("choice"):
        confidence = float(probabilities.get(answer["choice"], 0) or 0) or None
        return str(answer["choice"]), confidence, confidence is None or confidence < UNSURE_BELOW
    if kind == "score" and probabilities:
        best_rung, confidence = max(((int(k), float(v)) for k, v in probabilities.items()), key=lambda kv: kv[1])
        label = FIT_LABELS[best_rung] if 0 <= best_rung < len(FIT_LABELS) else None
        return label, confidence, confidence < UNSURE_BELOW
    return None, None, True


def receipts_from(component_id: str, response: DecisionResponse | None, question_names: list[str], *,
                  mode: str, evidence_ids: list[str], not_evaluated_reason: str | None = None) -> list[DecisionReceipt]:
    receipts = []
    for name in question_names:
        question_type, requirement_id = _question_type(name)
        answer = (response.answers.get(name) if response else None) or None
        engine = (response.model or "").lower() if response else ""
        band = next((b for name, b in BANDS.items() if engine.startswith(name)), UNSURE_BAND)
        final, confidence, unsure = _interpret(answer, band) if answer else (None, None, True)
        if final and question_type == "requirement_fit":
            final = {"yes": "meets", "no": "does_not_meet"}.get(final, final)
        receipts.append(DecisionReceipt(
            id=new_id(), created_at=utc_now(), candidate_id=component_id, requirement_id=requirement_id,
            question_type=question_type, rubric_version=RUBRIC_VERSION, evidence_ids=evidence_ids,
            jev_mode=mode, jev_model_id=response.model if response else None,
            returned_judgment=answer, reported_confidence=confidence,
            aggregation_policy=None if answer else f"not evaluated: {not_evaluated_reason or 'no answer returned'}",
            final_result=final, needs_review=unsure if answer else True,
        ))
    return receipts
