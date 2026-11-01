"""
The eligibility gate: may this component be recommended for reuse?

Plain Python, no model (IMPLEMENTATION_GUIDE.md 6.3, Lesson 22). The rules
run in a fixed order and the first hard rule that fires wins:

    1. strong copyleft or non-open license, under a permissive-only policy  -> excluded
    2. archived, when the policy excludes archived projects                 -> excluded
    3. a finished app or demo (the relevance judge's "reference only")      -> unresolved
    4. license missing, not retrieved or unrecognised                      -> review_required
    5. weak copyleft under a permissive-only policy                        -> review_required
    6. Jev says it does NOT meet any requirement it was asked about         -> unresolved
    otherwise                                                              -> eligible

The invariant (tested)
    Ranking sorts by eligibility tier FIRST, then by fit and adoption, so no
    score, however high, can lift an excluded or unresolved component above
    an eligible one.
"""

from dataclasses import dataclass
from typing import Any, Literal

from app.models.eligibility import EligibilityResult
from app.policy.licenses import license_family

POLICY_VERSION = "eligibility-2026-10-16.1"
TIER = {"eligible": 0, "review_required": 1, "unresolved": 2, "excluded": 3}


@dataclass(frozen=True)
class EligibilityPolicy:
    licenses: Literal["permissive", "copyleft_ok"] = "permissive"
    exclude_archived: bool = True


def check_component(component: dict[str, Any], receipts: list[dict[str, Any]], policy: EligibilityPolicy) -> EligibilityResult:
    """The gate's verdict for one component (as saved: a dict), given its decision receipts."""
    facts = component["facts"]
    license_text = facts.get("license")
    status = facts.get("license_status")
    family = license_family(license_text) if status in ("detected", "unrecognised") else "unknown"
    name = component["id"]

    def result(verdict: str, *reasons: str, by: Literal["rules", "decision_model"] = "rules") -> EligibilityResult:
        return EligibilityResult(repo=name, status=verdict, reasons=list(reasons), decided_by=by, policy_version=POLICY_VERSION)

    if policy.licenses == "permissive" and family in ("strong_copyleft", "non_open"):
        kind = "strong copyleft" if family == "strong_copyleft" else "not an open-source license"
        return result("excluded", f"license {license_text} is {kind}; the policy allows permissive licenses only")
    if policy.exclude_archived and facts.get("archived") is True:
        return result("excluded", "the repository is archived (no longer maintained)")
    if component.get("fit") == 1 or component.get("kind") == "reference_app":
        return result("unresolved", "a finished app or demo, to learn from, not a building block to reuse")
    if status in (None, "none_detected", "not_retrieved") or family == "unknown":
        why = {"none_detected": "no license was detected", "not_retrieved": "the license could not be retrieved"}.get(
            status, f"the license '{license_text}' was not recognised")
        return result("review_required", f"{why}; a person must check it before reuse")
    if policy.licenses == "permissive" and family == "weak_copyleft":
        return result("review_required", f"license {license_text} is weak copyleft: usable as a library with conditions")
    fit_answers = [r for r in receipts if r.get("question_type") == "requirement_fit" and r.get("final_result")]
    if fit_answers and all(r["final_result"] == "does_not_meet" for r in fit_answers):
        return result("unresolved", "the decision model judged that the evidence does not show it meets the requirement", by="decision_model")
    return result("eligible")


def rank_key(component: dict[str, Any], verdict: EligibilityResult) -> tuple:
    """Sort key: eligibility tier first (the invariant), then judged fit, then adoption."""
    facts = component["facts"]
    adoption = max((facts.get("stars") or 0) * 50, facts.get("downloads_last_month") or 0)
    return TIER[verdict.status], -(component.get("fit") or 2), -adoption
