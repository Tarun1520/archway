"""
Node: approve_version. Pauses for the final approval of ONE specific option version (interrupt 4 of 4).

    approve   that exact version is marked approved, and the run's options stage is done.
    change    a change request: it becomes the NEXT version of that option (draft_options, then review again).

The rule this node exists for (IMPLEMENTATION_GUIDE.md 7.4)
    Approval is tied to a version. A change makes a new version, and approval never transfers to it: the
    approved flag lives on the one version that was approved, and `approved_option` is cleared by the redraft.
"""

from typing import Literal

from langgraph.graph import END
from langgraph.runtime import Runtime
from langgraph.types import Command, interrupt

from app.graph import events
from app.graph.context import RunContext
from app.graph.state import WorkflowState
from app.models.option_flow import ApprovalDecision
from app.options.versions import presented

NODE = "approve_version"


async def approve_version(state: WorkflowState, runtime: Runtime[RunContext]) -> Command[Literal["draft_options", "__end__"]]:
    chosen = next((o for o in presented(state.get("options", [])) if o["id"] == state.get("selected_option_id")), None)
    if chosen is None:
        raise ValueError("there is no selected option to approve")
    reply = interrupt({"node": NODE, "option_id": chosen["id"], "version": chosen["version"]})

    emit = runtime.stream_writer
    decision = ApprovalDecision.model_validate(reply)
    if decision.action == "approve":
        options = [{**o, "approved": o["id"] == chosen["id"] and o["version"] == chosen["version"]} for o in state["options"]]
        emit(events.activity(f"Option {chosen['id']} version {chosen['version']} approved"))
        return Command(update={"options": options, "approved_option": {"id": chosen["id"], "version": chosen["version"]}}, goto=END)

    emit(events.activity(f"Change requested for {chosen['id']}: {decision.request}"))
    return Command(
        update={"revision": {"option_id": chosen["id"], "request": (decision.request or "").strip()}, "selected_option_id": None, "approved_option": None, "option_retries": 0,
                "plan_requested": False},  # a plan, if any, was for the old version: a new one is asked for again
        goto="draft_options",
    )
