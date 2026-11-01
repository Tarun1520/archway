"""
Lesson 22: Policy code (the eligibility gate) and why it is plain Python
========================================================================

What you learn here
    Rules that must ALWAYS hold are written as ordinary, boring functions:
    no model, no randomness. That makes them testable with certainty.

    This lesson builds a cut-down version of Archway's eligibility gate and a
    ranking function, with one invariant: an ineligible repository can never
    be ranked first, however high its suitability score is.

How to run (from the project root)
    backend/.venv/bin/python backend/learning/22_policy_gate.py
    and the tests:
    backend/.venv/bin/python -m pytest backend/learning/22_policy_gate_test.py -q

Where Archway uses this
    backend/app/policy/ in Phase 4. Section 6.3 of IMPLEMENTATION_GUIDE.md
    (the table) and Checkpoint 4: "An ineligible repository can never be
    ranked first (unit test)".
"""

from dataclasses import dataclass
from typing import Literal

Status = Literal["eligible", "review_required", "excluded", "unresolved"]

# The configured policy. In the real app this comes from settings.
ALLOWED_LICENSES = {"MIT", "Apache-2.0", "BSD-3-Clause"}
EXCLUDE_ARCHIVED = True


@dataclass(frozen=True)
class Repo:
    name: str
    license: str | None  # None = not retrieved / missing
    archived: bool | None  # None = not retrieved
    suitability: float  # judged fit, 0..1 (from a model; NOT trusted for rules)
    supports_required_feature: bool | None  # None = evidence does not say


@dataclass(frozen=True)
class Eligibility:
    status: Status
    reasons: tuple[str, ...]


def check_eligibility(repo: Repo) -> Eligibility:
    """Apply the rules in a fixed order. The first hard rule that fires wins."""
    # 1. Incompatible license: excluded, whatever else is true.
    if repo.license is not None and repo.license not in ALLOWED_LICENSES:
        return Eligibility("excluded", (f"license {repo.license} is not allowed by policy",))
    # 2. Archived (when policy says exclude).
    if EXCLUDE_ARCHIVED and repo.archived is True:
        return Eligibility("excluded", ("repository is archived",))
    # 3. Missing license: a person must look. NOT approved for reuse.
    if repo.license is None:
        return Eligibility("review_required", ("license not retrieved",))
    # 4. Required feature not supported by the evidence we have.
    if repo.supports_required_feature is not True:
        return Eligibility("unresolved", ("required feature not supported by available evidence",))
    return Eligibility("eligible", ())


def rank(repos: list[Repo]) -> list[tuple[Repo, Eligibility]]:
    """Order repositories for display.

    LEARNING NOTE: how the invariant is enforced
      The sort key is (eligibility tier, then suitability). Tier comes FIRST,
      so suitability can only reorder repositories WITHIN a tier. A score can
      never lift a lower tier above a higher one.
    """
    tier = {"eligible": 0, "review_required": 1, "unresolved": 2, "excluded": 3}
    checked = [(repo, check_eligibility(repo)) for repo in repos]
    return sorted(checked, key=lambda pair: (tier[pair[1].status], -pair[0].suitability))


if __name__ == "__main__":
    repos = [
        Repo("gpl-powerhouse", "GPL-3.0", False, 0.99, True),  # best fit, bad license
        Repo("no-license-gem", None, False, 0.95, True),
        Repo("archived-classic", "MIT", True, 0.90, True),
        Repo("solid-choice", "MIT", False, 0.70, True),
        Repo("unclear-feature", "Apache-2.0", False, 0.80, None),
    ]
    print(f"{'rank':4} {'repo':18} {'score':>5}  {'status':16} why")
    for position, (repo, result) in enumerate(rank(repos), start=1):
        print(f"{position:<4} {repo.name:18} {repo.suitability:>5}  {result.status:16} {'; '.join(result.reasons)}")
    print("\nThe 0.99-scoring repository ranks last because its license is excluded.")
