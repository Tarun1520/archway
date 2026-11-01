"""
What the options model is shown, and the lookups the code uses to check what it returns.

The line this file keeps
    The model is shown FACTS (license, activity, evidence ids), the gate's verdicts, and the decision
    model's answers (with WHICH engine answered: "laya/typed-decisions", "fixture", ...). It may only
    propose reusing a component that is listed as reusable here, by its id. Everything about a reused
    repository (its name, its license) is then filled in by code from the same facts, so the model cannot
    invent a repository or change a fact.

Only `eligible` components are reusable. The rest are listed with the reason, so the model does not
propose them (and the review gate would refuse them anyway).
"""

from typing import Any

EXCERPT_CHARS = 1500  # the reviewer checks claims against this text: a short one makes every claim look unsupported


def latest_by_id(components: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The same component can be proposed in two research rounds; keep the latest."""
    newest: dict[str, dict[str, Any]] = {}
    for component in components:
        newest[component["id"]] = component
    return list(newest.values())


def decision_view(receipts: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The decision model's answers about one component, in a few words each (None if it was never asked)."""
    if not receipts:
        return None
    fit = {r["requirement_id"]: r["final_result"] for r in receipts if r.get("question_type") == "requirement_fit" and r.get("requirement_id")}
    risk = next((r["final_result"] for r in receipts if r.get("question_type") == "integration_risk"), None)
    review = next((r["final_result"] for r in receipts if r.get("question_type") == "needs_human_review"), None)
    return {
        "engine": next((r["jev_model_id"] for r in receipts if r.get("jev_model_id")), None),
        "mode": receipts[0].get("jev_mode"),
        "fit_by_requirement": fit,
        "integration_risk": risk,
        "needs_human_review": review,
        "evaluated": any(r.get("final_result") for r in receipts),
    }


def verdicts_by_component(eligibility: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {item["component_id"]: item for item in eligibility}


def receipts_by_component(receipts: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for receipt in receipts:
        grouped.setdefault(receipt["candidate_id"], []).append(receipt)
    return grouped


def reusable_components(state: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """component id -> component, for the ones the gate says are `eligible`. Building blocks only."""
    verdicts = verdicts_by_component(state.get("eligibility", []))
    found = {}
    for component in latest_by_id(state.get("components", [])):
        verdict = verdicts.get(component["id"])
        if verdict and verdict["status"] == "eligible" and component.get("kind") != "reference_app" and component.get("fit") != 1:
            found[component["id"]] = component
    return found


def candidate_view(component: dict[str, Any], decision: dict[str, Any] | None) -> dict[str, Any]:
    facts = component["facts"]
    return {
        "id": component["id"], "capability_id": component["capability_id"], "name": component["name"],
        "approach": component.get("approach"), "provides": component["provides"], "fit_notes": component["fit_notes"],
        "concerns": component.get("concerns", []), "kind": component.get("kind"),
        "license": facts.get("license"), "source": facts.get("reference"), "stars": facts.get("stars"),
        "last_activity": str(facts["last_activity"]) if facts.get("last_activity") else None,
        "evidence_ids": facts.get("evidence_ids", []),
        "decision_model_answers": decision,
    }


def brief_view(brief: dict[str, Any]) -> dict[str, Any]:
    return {
        "version": brief.get("version"), "problem": brief.get("problem"), "users": brief.get("users"),
        "must_have": [{"id": r["id"], "text": r["text"]} for r in brief.get("must_have", [])],
        "nice_to_have": [{"id": r["id"], "text": r["text"]} for r in brief.get("nice_to_have", [])],
        "stack_preferences": brief.get("stack_preferences", []),
        "constraints": brief.get("constraints", {}),
        "assumptions": [a["text"] for a in brief.get("assumptions", [])],
        "unknowns": brief.get("unknowns", []),
    }


def material(state: dict[str, Any]) -> dict[str, Any]:
    """Everything the drafting model is shown about the researched ground."""
    receipts = receipts_by_component(state.get("receipts", []))
    reusable = reusable_components(state)
    verdicts = verdicts_by_component(state.get("eligibility", []))
    not_reusable = []
    for component in latest_by_id(state.get("components", [])):
        if component["id"] in reusable:
            continue
        verdict = verdicts.get(component["id"], {})
        not_reusable.append({
            "id": component["id"], "name": component["name"], "capability_id": component["capability_id"],
            "status": verdict.get("status", "unresolved"), "why": "; ".join(verdict.get("reasons", [])) or "not assessed",
        })
    return {
        "brief": brief_view(state.get("brief") or {}),
        "capabilities": [
            {"id": c["id"], "name": c["name"], "need": c["need"], "requirement_ids": c.get("requirement_ids", []),
             "approaches": c.get("approaches", []), "priority": c.get("priority", "core")}
            for c in state.get("capabilities", [])
        ],
        "reusable_components": [candidate_view(c, decision_view(receipts.get(c["id"], []))) for c in reusable.values()],
        "not_reusable_components": not_reusable,
        "research_notes": state.get("research_notes", []),
    }


def evidence_excerpts(state: dict[str, Any], ids: set[str]) -> list[dict[str, Any]]:
    """Short excerpts for the evidence ids an option cites, so the reviewer can check the claim against them."""
    found = []
    for item in state.get("evidence", []):
        if item["id"] in ids:
            found.append({"id": item["id"], "source": item.get("url"), "excerpt": (item.get("excerpt") or "")[:EXCERPT_CHARS]})
    return found
