"""
Node: confirm_brief. Pauses the run until the user approves the brief.

What this node does
    1. Pauses with `interrupt(...)`, saying which brief version is waiting.
    2. If the user sends an EDIT, it builds a new, unconfirmed version
       (conflicts are re-checked) and comes back to this same node, so the
       new version is what gets confirmed. An edit never carries approval.
    3. If the user APPROVES, it marks that exact version confirmed and sends
       the run on to the research stage (Phase 3).

Why research cannot start early
    The only way out of this node towards the research nodes is the
    "approve" branch, so they are unreachable until a brief is confirmed.

Learn more: LEARNING_GUIDE.md topics 11, 14 and 18.
"""

from typing import Literal

from langgraph.runtime import Runtime
from langgraph.types import Command, interrupt

from app.briefing.builder import apply_edit, mark_confirmed
from app.graph import events
from app.graph.context import RunContext
from app.graph.state import WorkflowState
from app.models.brief import ProjectBrief
from app.models.workflow import ConfirmDecision

NODE = "confirm_brief"
RESEARCH_ENTRY = "research_lead"  # the entry of app/graph/research_team.py


async def confirm_brief(state: WorkflowState, runtime: Runtime[RunContext]) -> Command[Literal["confirm_brief", "research_lead"]]:
    brief = ProjectBrief.model_validate(state["brief"])

    # Pause until the user decides. Nothing with a side effect sits above this
    # line, because the node runs again from the top when the run resumes.
    reply = interrupt({"node": NODE, "brief_version": brief.version})

    # ---- Everything below runs only after the user has replied --------------
    emit = runtime.stream_writer
    decision = ConfirmDecision.model_validate(reply)

    if decision.action == "edit":
        if decision.edit is None:
            raise ValueError("an edit decision must include the edited brief")
        edited = apply_edit(brief, decision.edit)
        emit(events.activity(f"Brief edited: version {edited.version} created (not yet confirmed)"))
        for conflict in edited.conflicts:
            emit(events.activity(f"Conflict flagged: {conflict.description}"))
        # goto this same node: the NEW version now waits for confirmation.
        return Command(update={"brief": edited.model_dump(mode="json")}, goto=NODE)

    confirmed = mark_confirmed(brief)
    emit(events.activity(f"Brief version {confirmed.version} confirmed"))
    # Approval is the ONLY way into the research stage.
    return Command(update={"brief": confirmed.model_dump(mode="json"), "brief_confirmed": True}, goto=RESEARCH_ENTRY)
