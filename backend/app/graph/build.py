"""
Wiring the nodes into the workflow graph.

What this file does
    One function, `build_workflow`, that lists the nodes and the arrows
    between them and returns the runnable graph.

The graph (Phases 2 and 3)

    START -> intake --(questions to ask)--> clarify --(answered)--> intake
                    \\                              \\--(skipped)--> confirm_brief
                     \\--(nothing to ask)--> confirm_brief --(edit)--> confirm_brief
                                                          \\--(approve)--> research_lead
                                                                  |
                         (the research TEAM of agents, app/graph/research_team.py)
               research_lead <-> capability_analyst / component_scout x N / project_scout / reviewer
                                                                  |
                                          finish_research -> evaluate_candidates -> END
                                          (Phase 4: decisions, receipts, eligibility gate)

    Phase 5, started by the person (a button after the shortlist; the service then sets `options_requested`):

        evaluate_candidates -> draft_options -> review_options --(failed, retries left)--> draft_options
                                                       \\--(done)--> select_or_revise --(revise)--> draft_options
                                                                              \\--(select)--> approve_version --(change)--> draft_options
                                                                                                    \\--(approve)--> END

    Phase 6, started by the person after approving one option version (a button; the service sets `plan_requested`):

        approve_version -> build_roadmap -> generate_prompts -> check_prompts --(failed, one retry)--> build_roadmap
                                                                       \\--(passed, or retry used)--> export -> END

    `clarify` and `confirm_brief` choose their own next node by returning a
    Command, so they need no outgoing edges here.

How to add a step later
    1. Write the node in app/graph/nodes/<name>.py
    2. Add one `builder.add_node(...)` line below
    3. Add the edge(s) that lead to it

Learn more: LEARNING_GUIDE.md topics 7, 9 and 10.
"""

from typing import Literal

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph

from app.graph.context import RunContext
from app.graph.nodes.clarify import clarify
from app.graph.nodes.approve_version import approve_version
from app.graph.nodes.build_roadmap import build_roadmap
from app.graph.nodes.check_prompts import check_prompts
from app.graph.nodes.export import export
from app.graph.nodes.generate_prompts import generate_prompts
from app.graph.nodes.confirm_brief import confirm_brief
from app.graph.nodes.draft_options import draft_options
from app.graph.nodes.evaluate_candidates import evaluate_candidates
from app.graph.nodes.intake import intake
from app.graph.nodes.review_options import review_options
from app.graph.nodes.select_or_revise import select_or_revise
from app.graph.research_team import add_research_team
from app.graph.state import WorkflowState


def route_after_intake(state: WorkflowState) -> Literal["clarify", "confirm_brief"]:
    """A router: it changes nothing, it only names the next node."""
    return "clarify" if state["open_questions"] else "confirm_brief"


def route_after_decisions(state: WorkflowState) -> Literal["draft_options", "__end__"]:
    """The run stops at the shortlist unless the person has asked for options (nothing is spent unasked)."""
    return "draft_options" if state.get("options_requested") else END


def route_after_approval(state: WorkflowState) -> list[str]:
    """After an approval the run rests, unless the person has asked for the build plan (nothing is spent unasked).

    LEARNING NOTE: an edge AND a Command from the same node
      approve_version chooses its own next step with a Command (END, or back to draft_options for a change). This
      edge adds one more possibility, read from the state: it is what lets the service start the plan later with
      update_state(as_node="approve_version"), exactly as the options stage is started after the shortlist.
      It returns a LIST of next nodes: an empty list adds nothing (the Command's own choice stands). Returning END
      here would draw a second "approve_version -> END" arrow next to the Command's one.
    """
    return ["build_roadmap"] if state.get("plan_requested") and state.get("approved_option") else []


def build_workflow(checkpointer: BaseCheckpointSaver | None = None):
    """Describe the graph and compile it.

    The checkpointer is plugged in here and nowhere else. The real app passes
    a SQLite saver (so runs survive a restart); a test may pass an in-memory
    one. The nodes do not know the difference.
    """
    builder = StateGraph(WorkflowState, context_schema=RunContext)

    builder.add_node("intake", intake)
    builder.add_node("clarify", clarify)
    builder.add_node("confirm_brief", confirm_brief)

    builder.add_edge(START, "intake")
    builder.add_conditional_edges("intake", route_after_intake)

    # confirm_brief sends an approved brief to the research lead, so the
    # research team cannot start until a brief has been confirmed.
    add_research_team(builder)
    # Phase 4: decisions and the eligibility gate, once research has finished.
    builder.add_node("evaluate_candidates", evaluate_candidates)
    builder.add_conditional_edges("evaluate_candidates", route_after_decisions)

    # Phase 5: architecture options. `review_options`, `select_or_revise` and `approve_version` choose their own
    # next node (they return a Command), so only the first arrow is drawn here.
    builder.add_node("draft_options", draft_options)
    builder.add_node("review_options", review_options)
    builder.add_node("select_or_revise", select_or_revise)
    builder.add_node("approve_version", approve_version)
    builder.add_edge("draft_options", "review_options")

    # Phase 6: the build plan. `check_prompts` chooses its own next node (a Command: retry or export).
    builder.add_node("build_roadmap", build_roadmap)
    builder.add_node("generate_prompts", generate_prompts)
    builder.add_node("check_prompts", check_prompts)
    builder.add_node("export", export)
    builder.add_conditional_edges("approve_version", route_after_approval, ["build_roadmap"])
    builder.add_edge("build_roadmap", "generate_prompts")
    builder.add_edge("generate_prompts", "check_prompts")
    builder.add_edge("export", END)

    return builder.compile(checkpointer=checkpointer)
