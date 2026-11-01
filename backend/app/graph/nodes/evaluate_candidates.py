"""
Node: evaluate_candidates. Phase 4: decisions and eligibility for every component.

What this node does, in order
    1. Picks the components worth asking about: building blocks whose license
       and maintenance do not already exclude them (asking about those would
       waste calls, since no answer could make them eligible).
    2. Asks the decision model (Jev) typed questions about each one, several
       components at a time: requirement fit (a score per requirement),
       integration risk (a choice), and whether a person should review it
       (yes/no). One request per component.
    3. Writes a DecisionReceipt for EVERY question, including the ones that
       could not be asked (service unavailable, call cap reached), marked
       "not evaluated" rather than guessed.
    4. Runs the deterministic eligibility gate on every component, using the
       receipts. The gate is plain Python and has the last word.

Live versus fixture
    In fixture mode the answers are fixed and every receipt says so. Live
    mode goes through Vercel AI Gateway (app/decisions/client.py).

Learn more: LEARNING_GUIDE.md topic 61, IMPLEMENTATION_GUIDE.md 6.3 and 6.4.
"""

import asyncio
from typing import Any

from langgraph.runtime import Runtime

from app.decisions.client import DecisionUnavailable
from app.decisions.questions import questions_for, state_for
from app.decisions.receipts import receipts_from
from app.graph import events
from app.graph.context import RunContext
from app.graph.state import WorkflowState
from app.policy.eligibility import EligibilityPolicy, check_component
from app.policy.licenses import license_family

NODE = "evaluate_candidates"
PARALLEL_REQUESTS = 4


def _latest_by_id(components: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The same component can be proposed in two rounds; keep its latest version."""
    latest: dict[str, dict[str, Any]] = {}
    for component in components:
        latest[component["id"]] = component
    return list(latest.values())


def _worth_asking(component: dict[str, Any], policy: EligibilityPolicy) -> bool:
    facts = component["facts"]
    if component.get("fit") == 1 or component.get("kind") == "reference_app":
        return False
    if policy.exclude_archived and facts.get("archived") is True:
        return False
    family = license_family(facts.get("license")) if facts.get("license_status") == "detected" else "unknown"
    return not (policy.licenses == "permissive" and family in ("strong_copyleft", "non_open"))


async def evaluate_candidates(state: WorkflowState, runtime: Runtime[RunContext]) -> dict:
    emit = runtime.stream_writer
    emit(events.node_started(NODE))
    context = runtime.context
    client = context.decisions
    policy = context.eligibility_policy or EligibilityPolicy()

    components = _latest_by_id(state["components"])
    capabilities = {c["id"]: c for c in state["capabilities"]}
    brief = state["brief"] or {}
    must = {r["id"]: r["text"] for r in brief.get("must_have", [])}
    constraints = [*(brief.get("constraints", {}).get("stated") or []),
                   *[v for k, v in (brief.get("constraints") or {}).items() if k != "stated" and isinstance(v, str)]]
    excerpts = {e["id"]: e.get("excerpt") for e in state["evidence"] if e.get("excerpt")}

    to_ask = [c for c in components if client is not None and _worth_asking(c, policy)]
    budget_left = max(0, context.max_jev_calls - state.get("jev_calls", 0))
    asked, skipped = to_ask[:budget_left], to_ask[budget_left:]
    notes: list[str] = []
    receipts: dict[str, list[dict[str, Any]]] = {}
    unavailable: str | None = None
    gate = asyncio.Semaphore(PARALLEL_REQUESTS)
    calls = 0

    async def ask(component: dict[str, Any]) -> None:
        nonlocal unavailable, calls
        capability = capabilities.get(component["capability_id"], {"name": "", "need": "", "requirement_ids": []})
        requirements = [{"id": r, "text": must[r]} for r in capability.get("requirement_ids", []) if r in must]
        if not requirements:
            requirements = [{"id": capability.get("id", "CAP"), "text": capability.get("need", "")}]
        questions = questions_for(component, requirements)
        evidence_ids = component["facts"].get("evidence_ids", [])
        state_view = state_for(component, capability, constraints, [excerpts[i] for i in evidence_ids if i in excerpts])
        response, reason = None, unavailable
        if unavailable is None:
            async with gate:
                try:
                    response = await client.decide(state=state_view, questions=questions)
                    calls += 1
                    emit(events.usage(service="jev", mode=client.mode, model=response.model, tokens=(
                        (response.input_tokens or 0) + (response.output_tokens or 0)) or None))
                except DecisionUnavailable as error:
                    unavailable = reason = str(error)
        receipts[component["id"]] = [r.model_dump(mode="json") for r in receipts_from(
            component["id"], response, list(questions), mode=client.mode, evidence_ids=evidence_ids,
            not_evaluated_reason=reason or unavailable)]

    if asked:
        emit(events.activity(f"Decisions: asking {client.mode} decision model about {len(asked)} components"))
        await asyncio.gather(*(ask(c) for c in asked))
    if unavailable:
        notes.append(f"Decisions not evaluated: {unavailable}. Eligibility used the rules alone.")
        emit(events.activity("Decision service unavailable: decisions marked not evaluated"))
    if skipped:
        notes.append(f"Decision call cap reached: {len(skipped)} components were not evaluated.")

    eligibility = []
    for component in components:
        verdict = check_component(component, receipts.get(component["id"], []), policy)
        eligibility.append({**verdict.model_dump(mode="json"), "component_id": component["id"]})
    counts = {s: sum(1 for e in eligibility if e["status"] == s) for s in ("eligible", "review_required", "unresolved", "excluded")}
    emit(events.activity("Eligibility: " + ", ".join(f"{n} {s.replace('_', ' ')}" for s, n in counts.items())))

    return {
        "eligibility": eligibility,
        "receipts": [r for rs in receipts.values() for r in rs],
        "jev_calls": state.get("jev_calls", 0) + calls,
        "research_notes": notes,
        "decisions_finished": True,
    }
