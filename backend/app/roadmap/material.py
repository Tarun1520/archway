"""
What the planning model is shown, and the lookups the code uses to check (and fill in) what it returns.

The line this file keeps (the same as for the options, app/options/material.py)
    The model is shown the APPROVED option version, the brief it was drafted from, and the facts about every
    component that option reuses (license, eligibility, evidence ids). It plans the work. It does not get to
    change a fact: licenses, repositories and evidence links in the prompts are copied by code from the same
    facts.

The option's validation tasks are numbered here (V-1, V-2 ...), so the model can say which spike settles which
one, and code can check that every one of them is settled before the work that depends on it.
"""

from typing import Any

from app.options.material import brief_view, latest_by_id, verdicts_by_component
from app.options.versions import presented


def approved_option(state: dict[str, Any]) -> dict[str, Any] | None:
    """The option version that was approved, or None (the plan stage refuses to start without one)."""
    approved = state.get("approved_option")
    if not approved:
        return None
    return next((o for o in state.get("options", []) if o["id"] == approved["id"] and o["version"] == approved["version"]), None)


def validation_tasks(option: dict[str, Any]) -> dict[str, str]:
    """"V-1" -> the option's first validation task, and so on."""
    return {f"V-{number}": text for number, text in enumerate(option.get("validation_tasks", []), start=1)}


def reused_facts(state: dict[str, Any], option: dict[str, Any]) -> list[dict[str, Any]]:
    """The facts about each component the option reuses: what the prompts may depend on, and with which caveats."""
    components = {c["id"]: c for c in latest_by_id(state.get("components", []))}
    verdicts = verdicts_by_component(state.get("eligibility", []))
    found = []
    for part in option.get("components", []):
        if part.get("kind") != "reuse":
            continue
        component = components.get(part.get("candidate_id") or "", {})
        facts = component.get("facts", {})
        verdict = verdicts.get(part.get("candidate_id") or "", {})
        found.append({
            "name": part["name"], "repo": part.get("repo"), "candidate_id": part.get("candidate_id"),
            "license": facts.get("license"), "license_status": facts.get("license_status"),
            "url": facts.get("url"), "eligibility": verdict.get("status", "unresolved"),
            "eligibility_reasons": verdict.get("reasons", []), "evidence_ids": facts.get("evidence_ids", []),
        })
    return found


def alternatives(state: dict[str, Any], option: dict[str, Any]) -> list[dict[str, Any]]:
    """The other options that were on offer (their latest passed versions): the rejected alternatives."""
    return [
        {"id": o["id"], "version": o["version"], "name": o.get("name"), "trade_off": o.get("trade_off"), "avoid_if": o.get("avoid_if")}
        for o in presented(state.get("options", [])) if o["id"] != option["id"]
    ]


def option_view(option: dict[str, Any]) -> dict[str, Any]:
    keys = ("id", "version", "name", "summary", "trade_off", "components", "integration_boundaries", "data_flow",
            "storage_model", "deployment", "security_privacy", "testing_approach", "risks", "requirement_coverage")
    return {key: option.get(key) for key in keys}


def material(state: dict[str, Any]) -> dict[str, Any]:
    """Everything the planning model is shown."""
    option = approved_option(state)
    if option is None:
        raise ValueError("there is no approved option version to plan")
    return {
        "brief": brief_view(state.get("brief") or {}),
        "approved_option": option_view(option),
        "validation_tasks": [{"id": key, "text": text} for key, text in validation_tasks(option).items()],
        "reused_components": reused_facts(state, option),
        "rejected_options": alternatives(state, option),
    }
