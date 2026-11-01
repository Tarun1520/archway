"""
Lesson 03: Conditional edges, loops, and stopping on purpose
============================================================

What you learn here
    - A CONDITIONAL EDGE picks the next node at run time by calling a small
      "router" function that looks at the state.
    - A LOOP is simply an edge that points back to an earlier node.
    - Every loop needs a limit that YOUR code enforces, plus a path for
      "we ran out of attempts" that ends honestly.

How to run (from the project root)
    backend/.venv/bin/python backend/learning/03_routing_and_loops.py

Where Archway uses this
    This is a small copy of the real `sufficiency_check` step:
      enough evidence        -> draft architecture options
      not enough, under limit -> research again
      not enough, limit hit   -> abstain ("insufficient evidence")
"""

from typing import Literal, TypedDict

from langgraph.errors import GraphRecursionError
from langgraph.graph import END, START, StateGraph

# A configurable limit. In the real app this comes from configuration.
MAX_RESEARCH_ROUNDS = 2
EVIDENCE_NEEDED = 5


class State(TypedDict):
    evidence_per_round: int  # pretend input: how much each search finds
    evidence_count: int
    research_rounds: int
    outcome: str


def research(state: State) -> dict:
    """Pretend to research: add some evidence and count the round."""
    return {
        "evidence_count": state["evidence_count"] + state["evidence_per_round"],
        "research_rounds": state["research_rounds"] + 1,
    }


def draft_options(state: State) -> dict:
    return {"outcome": f"options drafted from {state['evidence_count']} evidence items"}


def abstain(state: State) -> dict:
    return {
        "outcome": (
            f"abstained: only {state['evidence_count']} of {EVIDENCE_NEEDED} "
            f"evidence items after {state['research_rounds']} rounds"
        )
    }


# LEARNING NOTE: the router
#   A router is NOT a node. It does not change state. It only returns the
#   NAME of the node to go to next. The Literal[...] return type lists every
#   place it can go, which lets LangGraph draw the graph correctly.
#
#   Notice this is plain Python with plain numbers. The decision "should we
#   keep spending calls?" is policy, so it lives in code, not in a model.
def route_after_research(state: State) -> Literal["research", "draft_options", "abstain"]:
    if state["evidence_count"] >= EVIDENCE_NEEDED:
        return "draft_options"
    if state["research_rounds"] < MAX_RESEARCH_ROUNDS:
        return "research"  # loop back
    return "abstain"


def build_graph():
    builder = StateGraph(State)
    builder.add_node("research", research)
    builder.add_node("draft_options", draft_options)
    builder.add_node("abstain", abstain)

    builder.add_edge(START, "research")
    # After "research" finishes, call the router to choose the next node.
    builder.add_conditional_edges("research", route_after_research)
    builder.add_edge("draft_options", END)
    builder.add_edge("abstain", END)
    return builder.compile()


def run(evidence_per_round: int) -> None:
    start = {
        "evidence_per_round": evidence_per_round,
        "evidence_count": 0,
        "research_rounds": 0,
        "outcome": "",
    }
    final = build_graph().invoke(start)
    print(f"  finds {evidence_per_round} per round -> {final['outcome']}")


if __name__ == "__main__":
    print("Three runs of the same graph, three different paths:")
    run(evidence_per_round=6)  # enough after round 1
    run(evidence_per_round=3)  # enough after round 2 (one loop)
    run(evidence_per_round=1)  # never enough: stops at the limit and abstains

    # LEARNING NOTE: LangGraph's own safety net
    #   If your own limit had a bug and the loop never ended, LangGraph would
    #   stop the run after `recursion_limit` steps and raise an error. That is
    #   a seat belt, not a design: always write your own limit as well.
    print("\nForcing LangGraph's safety net with a tiny recursion_limit:")
    try:
        build_graph().invoke(
            {"evidence_per_round": 1, "evidence_count": 0, "research_rounds": 0, "outcome": ""},
            config={"recursion_limit": 1},
        )
    except GraphRecursionError as error:
        print("  GraphRecursionError:", str(error).splitlines()[0])
