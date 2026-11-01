"""
Helpers every agent node uses: reading the shared board, preparing an
agent's tools, and writing its results back.

LEARNING NOTE: the two halves of an agent node
    An agent NODE (a box in the main workflow) does three things:
      1. reads what it needs from the shared state (the "board")
      2. runs its agent loop (app/agents/runtime.py) with a briefing
      3. turns the agent's report into state updates and a team message
    Steps 1 and 3 are the same for every agent, so they live here.
"""

import json
from typing import Any

from langgraph.runtime import Runtime

from app.evidence.urls import find_urls
from app.graph.context import RunContext
from app.models.brief import ProjectBrief
from app.models.common import new_id, utc_now
from app.models.research import Capability, ComponentCandidate, ReviewVerdict, SimilarProject, SourceFacts, TeamMessage
from app.tools.base import BoardView, ToolContext


def board_from(state: dict[str, Any]) -> BoardView:
    """The board as the agents see it. Works on the full state or on a Send payload."""
    rounds: dict[str, int] = {}
    for capability_id in state.get("scout_rounds", []):
        rounds[capability_id] = rounds.get(capability_id, 0) + 1
    review = ReviewVerdict.model_validate(state["review"]) if state.get("review") else None
    capabilities = [Capability.model_validate(c) for c in state.get("capabilities", [])]
    core = {c.id for c in capabilities if c.priority == "core"}
    core_rounds = sum(n for cid, n in rounds.items() if cid in core)
    return BoardView(
        brief=ProjectBrief.model_validate(state["brief"]),
        capabilities=capabilities,
        components=[ComponentCandidate.model_validate(c) for c in state.get("components", [])],
        projects=[SimilarProject.model_validate(p) for p in state.get("projects", [])],
        review=review,
        # A review is current when it has seen every CORE scouting round
        # (supporting capabilities are scouted after the core review, once).
        review_is_fresh=review is not None and review.scouting_seen == core_rounds,
        scout_rounds=rounds,
        user_urls=find_urls(state.get("user_texts", [])),
    )


def facts_index(state: dict[str, Any]) -> dict[str, SourceFacts]:
    """Every source looked at so far. Inspected facts win over search-only facts."""
    index: dict[str, SourceFacts] = {}
    for data in state.get("source_facts", []):
        facts = SourceFacts.model_validate(data)
        key = f"{facts.kind}:{facts.reference.lower()}"
        if key not in index or facts.inspected or not index[key].inspected:
            index[key] = facts
    return index


def tool_context(state: dict[str, Any], runtime: Runtime[RunContext], assignment: dict | None = None) -> ToolContext:
    context = runtime.context
    if context.integrations is None or context.budget is None:
        raise RuntimeError("the run context has no research integrations or budget")
    return ToolContext(
        integrations=context.integrations, budget=context.budget, board=board_from(state),
        mode=context.integrations.github.mode, emit=runtime.stream_writer,
        assignment=assignment or {}, facts=facts_index(state),
    )


def message(sender: str, recipient: str, kind: str, content: str, capability_ids: list[str] | None = None) -> dict:
    """One message on the team channel, ready for the state."""
    return TeamMessage(
        id=new_id(), sender=sender, recipient=recipient, kind=kind, content=content.strip()[:1500],
        capability_ids=capability_ids or [], created_at=utc_now(),
    ).model_dump(mode="json")


def produced(tools: ToolContext) -> dict[str, Any]:
    """What an agent's tools retrieved, as state updates (evidence, facts, notes)."""
    return {
        "evidence": [item.model_dump(mode="json") for item in tools.evidence],
        "repos": [repo.model_dump(mode="json") for repo in tools.repos],
        "source_facts": [facts.model_dump(mode="json") for facts in tools.new_facts],
        "research_notes": list(dict.fromkeys(tools.notes)),
    }


def brief_material(brief: ProjectBrief) -> dict[str, Any]:
    """The parts of the brief an agent needs, kept short."""
    return {
        "problem": brief.problem,
        "users": brief.users,
        "must_have": [{"id": r.id, "text": r.text} for r in brief.must_have],
        "nice_to_have": [r.text for r in brief.nice_to_have],
        "stack_preferences": brief.stack_preferences,
        "constraints": brief.constraints.model_dump(),
    }


def tagged(tag: str, data: Any) -> str:
    """Wrap material in clear tags. Inside the tags is data, never instructions."""
    return f"<{tag}>\n{json.dumps(data, ensure_ascii=False, indent=1, default=str)}\n</{tag}>"
