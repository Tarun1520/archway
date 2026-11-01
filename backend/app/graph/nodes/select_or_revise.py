"""
Node: select_or_revise. Pauses until the person picks an option or asks for a change (interrupt 3 of 4).

    select   the chosen option (one that passed review) goes to `approve_version`
    revise   a change request. For ONE option it becomes that option's NEXT VERSION (draft_options, then the review
             gate again). With nothing presented ("no recommendation") the request guides a fresh draft.

Nothing above the interrupt() call has a side effect, because the node runs again from the top on resume.
"""

from typing import Literal

from langgraph.runtime import Runtime
from langgraph.types import Command, interrupt

from app.graph import events
from app.graph.context import RunContext
from app.graph.state import WorkflowState
from app.models.option_flow import OptionDecision
from app.options.versions import presented

NODE = "select_or_revise"


async def select_or_revise(state: WorkflowState, runtime: Runtime[RunContext]) -> Command[Literal["approve_version", "draft_options"]]:
    shown = presented(state.get("options", []))
    reply = interrupt({
        "node": NODE,
        "presented": [{"id": o["id"], "version": o["version"]} for o in shown],
        "no_recommendation": not shown,
    })

    emit = runtime.stream_writer
    decision = OptionDecision.model_validate(reply)
    if decision.action == "select":
        chosen = next((o for o in shown if o["id"] == decision.option_id), None)
        if chosen is None:
            raise ValueError(f"{decision.option_id} is not one of the options on offer")
        emit(events.activity(f"Option {chosen['id']} (version {chosen['version']}) selected, waiting for approval"))
        return Command(update={"selected_option_id": chosen["id"]}, goto="approve_version")

    target = decision.option_id if decision.option_id and any(o["id"] == decision.option_id for o in shown) else None
    emit(events.activity(f"Change requested{f' for {target}' if target else ''}: {decision.request}"))
    return Command(
        update={"revision": {"option_id": target, "request": (decision.request or "").strip()}, "selected_option_id": None, "option_retries": 0},
        goto="draft_options",
    )
