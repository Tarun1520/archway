"""
The review gate for options (IMPLEMENTATION_GUIDE.md 7.3): plain code first, then a model's findings.

Who decides what
    RULES (this file, plain Python, no model) decide the things that must always hold:
      - every reused repository is a component the gate marked `eligible`   (the invariant)
      - nothing is reused without naming a real researched component
      - an option has components, pros AND cons
    The reviewing MODEL adds what code cannot judge (a broken stated constraint, a contradiction, a claim the
    cited evidence does not support). Its `unsupported_claim` findings never reject an option: they become
    VALIDATION TASKS, so an unproven compatibility claim is shown as something to check, not as a fact.

An option passes when it has no blocking issue. If the model check could not run, the review says so
(`llm_checked: false`); an option is then judged by the rules alone and labelled that way.
"""

from typing import Any, Literal

from app.models.brief_draft import StrictModel
from app.options.material import verdicts_by_component

MAX_COMPONENTS_BEFORE_WARNING = 8


class ModelIssue(StrictModel):
    option_id: str
    severity: Literal["blocking", "warning"]
    kind: Literal["constraint", "unsupported_claim", "contradiction", "overengineering", "license", "coverage", "citation"]
    text: str


class ModelReview(StrictModel):
    issues: list[ModelIssue]


def _issue(severity: str, kind: str, text: str, source: str) -> dict[str, str]:
    return {"severity": severity, "kind": kind, "text": text, "source": source}


def rule_issues(option: dict[str, Any], state: dict[str, Any], build_problems: list[str]) -> list[dict[str, str]]:
    """What plain code finds wrong with one option. Nothing here asks a model."""
    issues = [_issue("blocking", "reuse_not_available", text, "rules") for text in build_problems]
    verdicts = verdicts_by_component(state.get("eligibility", []))
    for part in option.get("components", []):
        if part["kind"] != "reuse":
            continue
        verdict = verdicts.get(part.get("candidate_id") or "")
        if verdict is None or verdict["status"] != "eligible":
            status = verdict["status"].replace("_", " ") if verdict else "not assessed"
            issues.append(_issue(
                "blocking", "reuse_not_eligible",
                f"'{part['name']}' reuses {part.get('repo')}, which the eligibility gate marks as {status}: only eligible repositories may be reused",
                "rules",
            ))
    if not option.get("components"):
        issues.append(_issue("blocking", "no_components", "the option lists no components", "rules"))
    if not option.get("pros"):
        issues.append(_issue("blocking", "missing_pros", "the option lists no pros", "rules"))
    if not option.get("cons"):
        issues.append(_issue("blocking", "missing_cons", "the option lists no cons: every option has a cost", "rules"))
    for requirement_id, coverage in option.get("requirement_coverage", {}).items():
        if coverage == "not_covered":
            issues.append(_issue("warning", "requirement_not_covered", f"{requirement_id} is not covered by this option", "rules"))
    reuses = [p for p in option.get("components", []) if p["kind"] == "reuse"]
    if reuses and not option.get("evidence_ids"):
        issues.append(_issue("warning", "no_evidence", "the option reuses components but cites no evidence", "rules"))
    if len(option.get("components", [])) > MAX_COMPONENTS_BEFORE_WARNING:
        issues.append(_issue("warning", "many_components", f"the option has {len(option['components'])} components: check it is not more than the brief needs", "rules"))
    return issues


def apply_review(option: dict[str, Any], rules: list[dict[str, str]], model: list[ModelIssue] | None) -> dict[str, Any]:
    """The option with its review attached. `model` is None when the model check did not run."""
    issues = list(rules)
    validation_tasks = list(option.get("validation_tasks", []))
    for found in model or []:
        if found.kind == "unsupported_claim":
            task = f"Validate: {found.text.strip()}"
            if task not in validation_tasks:
                validation_tasks.append(task)  # an unproven claim becomes something to check
            continue
        issues.append(_issue(found.severity, found.kind, found.text.strip(), "model"))
    passed = not any(i["severity"] == "blocking" for i in issues)
    return {**option, "validation_tasks": validation_tasks, "review": {"passed": passed, "issues": issues, "llm_checked": model is not None}}


def feedback_for(option: dict[str, Any]) -> list[str]:
    """What a redraft is told is wrong: the blocking issues, in plain words."""
    return [i["text"] for i in (option.get("review") or {}).get("issues", []) if i["severity"] == "blocking"]
