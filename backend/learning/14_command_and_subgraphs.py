"""
Lesson 14: Command (update + route in one step) and subgraphs
=============================================================

What you learn here
    1. COMMAND: a node can return `Command(update=..., goto=...)` to change
       the state AND choose the next node in one return value, so you do not
       need a separate router function.
    2. SUBGRAPH: a whole compiled graph can be used as ONE node inside a
       bigger graph. This is how you keep a large workflow in small files.

How to run (from the project root)
    backend/.venv/bin/python backend/learning/14_command_and_subgraphs.py

Where Archway uses this
    - Command: the `sufficiency_check` step decides "research again, draft
      options, or abstain" and records why, in one place.
    - Subgraphs: the research stage (plan -> search -> inspect -> normalise)
      can be its own small graph living in its own file, plugged into the
      main workflow as a single node.
"""

import operator
from typing import Annotated, Literal, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

MAX_ROUNDS = 2
EVIDENCE_NEEDED = 5


# -----------------------------------------------------------------------------
# PART 1: Command
# -----------------------------------------------------------------------------
class State(TypedDict):
    evidence_count: int
    rounds: int
    # The reducer from Lesson 02: every node's note is appended to the list.
    trail: Annotated[list[str], operator.add]


def research(state: State) -> dict:
    return {
        "evidence_count": state["evidence_count"] + 2,
        "rounds": state["rounds"] + 1,
        "trail": [f"research round {state['rounds'] + 1}"],
    }


# LEARNING NOTE: the return annotation is important.
#   `Command[Literal[...]]` lists the nodes this one may send the run to.
#   LangGraph reads it to draw the graph correctly. Without it the graph
#   still runs, but drawings will not show these arrows.
def sufficiency_check(
    state: State,
) -> Command[Literal["research", "draft_options", "abstain"]]:
    if state["evidence_count"] >= EVIDENCE_NEEDED:
        goto, why = "draft_options", "enough evidence"
    elif state["rounds"] < MAX_ROUNDS:
        goto, why = "research", "not enough yet, rounds left"
    else:
        goto, why = "abstain", "not enough and out of rounds"
    # One return value does two jobs: write to the state AND pick the route.
    return Command(update={"trail": [f"check: {why}"]}, goto=goto)


def draft_options(state: State) -> dict:
    return {"trail": ["options drafted"]}


def abstain(state: State) -> dict:
    return {"trail": ["abstained honestly"]}


def build_command_graph():
    builder = StateGraph(State)
    builder.add_node("research", research)
    builder.add_node("sufficiency_check", sufficiency_check)
    builder.add_node("draft_options", draft_options)
    builder.add_node("abstain", abstain)
    builder.add_edge(START, "research")
    builder.add_edge("research", "sufficiency_check")
    # NOTE: there is no add_conditional_edges for sufficiency_check. Its
    # Command(goto=...) already says where to go next.
    builder.add_edge("draft_options", END)
    builder.add_edge("abstain", END)
    return builder.compile()


# -----------------------------------------------------------------------------
# PART 2: a subgraph used as a node
# -----------------------------------------------------------------------------
class ResearchState(TypedDict):
    query: str
    candidates: list[str]


def search(state: ResearchState) -> dict:
    return {"candidates": [f"{state['query']}-repo-{n}" for n in (1, 2, 3)]}


def keep_top_two(state: ResearchState) -> dict:
    return {"candidates": state["candidates"][:2]}


def build_research_subgraph():
    """A complete little graph. It could live in its own file."""
    builder = StateGraph(ResearchState)
    builder.add_node("search", search)
    builder.add_node("keep_top_two", keep_top_two)
    builder.add_edge(START, "search")
    builder.add_edge("search", "keep_top_two")
    builder.add_edge("keep_top_two", END)
    return builder.compile()


class ParentState(TypedDict):
    query: str
    candidates: list[str]  # same key name as in the subgraph: this is the link
    report: str


def write_report(state: ParentState) -> dict:
    return {"report": f"{len(state['candidates'])} candidates kept: {state['candidates']}"}


def build_parent_graph():
    builder = StateGraph(ParentState)
    # LEARNING NOTE: how the two graphs share data
    #   When parent and subgraph use the SAME key names (query, candidates),
    #   those keys flow in and out automatically. Keys that exist in only one
    #   of them stay private to it.
    builder.add_node("research", build_research_subgraph())  # a graph as a node
    builder.add_node("write_report", write_report)
    builder.add_edge(START, "research")
    builder.add_edge("research", "write_report")
    builder.add_edge("write_report", END)
    return builder.compile()


if __name__ == "__main__":
    print("PART 1: Command picks the route and records why")
    for per_round_note, start_count in (("starts with 4", 4), ("starts with 0", 0), ("starts with -4", -4)):
        final = build_command_graph().invoke({"evidence_count": start_count, "rounds": 0, "trail": []})
        print(f"  {per_round_note:15} -> {' | '.join(final['trail'])}")

    print("\nPART 2: a subgraph is just a node")
    final = build_parent_graph().invoke({"query": "notes", "candidates": [], "report": ""})
    print("  ", final["report"])

    print("\nThe parent graph, drawn (the subgraph shows as one box):")
    print(build_parent_graph().get_graph().draw_mermaid())
