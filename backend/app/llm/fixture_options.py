"""
Scripted answers for the options stage, for FIXTURE mode (offline, free, repeatable).

NOT intelligence. It builds options by simple rules from the components listed as reusable in the prompt's
material: one that reuses the first component of each capability, and (only when there are at least two reusable
components) a leaner one that reuses just one. Every text says FIXTURE. A revision swaps the last reused
component for your own code. The review finds no issues.

Its job is to let the whole options stage run in tests and offline, with the same shape of answers a real model
gives, so the code around the model (versions, review gate, approval) is exercised for real.
"""

import json
import re
from typing import Any

NOTE = "FIXTURE: written by simple rules, not by a model."
DIMENSIONS = ("simplicity", "effort", "oss_reuse", "integration_risk", "maintainability", "privacy", "cost_exposure", "evidence_coverage")


def _material(user_text: str) -> dict[str, Any]:
    match = re.search(r"<material>\s*(\{.*?\})\s*</material>", user_text, re.DOTALL)
    return json.loads(match.group(1)) if match else {}


def _json_block(user_text: str, tag: str) -> Any:
    match = re.search(rf"<{tag}>\s*(.*?)\s*</{tag}>", user_text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except ValueError:
        return None


def _option(key: str, name: str, trade_off: str, reuse: list[dict[str, Any]], material: dict[str, Any], change: str | None = None) -> dict[str, Any]:
    parts = [
        {"name": c["name"], "responsibility": c["provides"][:160] or "provides a core capability", "kind": "reuse", "candidate_id": c["id"]}
        for c in reuse
    ]
    parts.append({"name": "Glue code", "responsibility": "Connects the parts and holds the product's own logic", "kind": "build", "candidate_id": None})
    evidence = [e for c in reuse for e in c.get("evidence_ids", [])]
    labels = ["App"] + [c["name"].split("/")[-1][:20] for c in reuse]
    mermaid = "flowchart LR\n" + "\n".join(f"  A[{labels[0]}] --> N{i}[{label}]" for i, label in enumerate(labels[1:])) if len(labels) > 1 else "flowchart LR\n  A[App]"
    return {
        "key": key, "name": name, "trade_off": trade_off, "summary": f"{NOTE} {name}: reuses {len(reuse)} researched component(s).",
        "coverage": [{"requirement_id": r["id"], "coverage": "partial", "note": NOTE} for r in material.get("brief", {}).get("must_have", [])],
        "components": parts,
        "integration_boundaries": f"{NOTE} The app calls each reused component through its public interface.",
        "data_flow": f"{NOTE} Input goes through the reused components in order.", "storage_model": f"{NOTE} A local database.",
        "deployment": f"{NOTE} Runs locally.", "security_privacy": f"{NOTE} Data stays on the machine.",
        "testing_approach": f"{NOTE} Unit tests around the glue code.",
        "risks": [f"{NOTE} Components may change their interfaces."],
        "validation_tasks": ["Confirm the reused components work together on a small sample."] if reuse else [],
        "mermaid": mermaid, "evidence_ids": evidence,
        "pros": [f"{NOTE} Reuses maintained components."] if reuse else [f"{NOTE} No external dependencies."],
        "cons": [f"{NOTE} More integration work."] if reuse else [f"{NOTE} More code to write."],
        "choose_if": f"{NOTE} You want less custom code.", "avoid_if": f"{NOTE} You cannot depend on outside projects.",
        "comparison": [{"dimension": d, "rating": "mixed", "note": NOTE} for d in DIMENSIONS],
        "change_summary": change,
    }


def fixture_draft(user_text: str) -> dict[str, Any]:
    material = _material(user_text)
    reusable = material.get("reusable_components", [])
    mode = (re.match(r"Mode:\s*(\w+)", user_text) or [None, "NEW"])[1].upper()

    if mode == "REVISE":
        previous = _json_block(user_text, "previous_option") or {}
        keep = [p["candidate_id"] for p in previous.get("components", []) if p.get("kind") == "reuse"][:-1]
        reuse = [c for c in reusable if c["id"] in keep]
        return {"options": [_option(previous.get("id", "OPT-1"), previous.get("name", "Option"), previous.get("trade_off") or "revised", reuse, material,
                                    change=f"{NOTE} Replaced the last reused component with your own code, so there is one dependency fewer.")],
                "no_recommendation_reason": None}
    if mode == "FIX":
        failed = _json_block(user_text, "failed_options") or []
        return {"options": [_option(f["id"], f.get("name", "Option"), f.get("trade_off") or "fixed", reusable[:1], material) for f in failed],
                "no_recommendation_reason": None}

    if not reusable:
        return {"options": [], "no_recommendation_reason": f"{NOTE} No component passed the eligibility gate, so nothing can be reused."}
    first_per_capability: dict[str, dict[str, Any]] = {}
    for component in reusable:
        first_per_capability.setdefault(component["capability_id"], component)
    options = [_option("A", "Reuse-first", "Most reuse, more integration work", list(first_per_capability.values())[:4], material)]
    if len(reusable) >= 2:
        options.append(_option("B", "Lean", "Fewest dependencies, more code to write", reusable[:1], material))
    return {"options": options, "no_recommendation_reason": None}


def fixture_review(user_text: str) -> dict[str, Any]:
    return {"issues": []}
