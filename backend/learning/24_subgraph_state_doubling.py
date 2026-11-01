"""
Lesson 24: A pitfall found while building Phase 3 (subgraphs that share state)
==============================================================================

What you learn here
    Lesson 14 showed that a compiled graph can be a node inside another
    graph, and said "keys with the same name flow in and out". That is true,
    and it hides a trap:

        The subgraph hands back its WHOLE state, not only what it changed.
        If a key has an append reducer (Lesson 02), the parent appends the
        returned list to the list it already has. Existing items appear twice.

How to run (from the project root)
    backend/.venv/bin/python backend/learning/24_subgraph_state_doubling.py

Where Archway uses this
    Phase 3's research stage was planned as a subgraph. This lesson is the
    experiment that showed why it was added to the main graph instead
    (app/graph/research.py explains). The same lists, `user_texts` and the
    research results, would have been doubled.

The fixes, and which one Archway chose
    1. Do not share keys: give the subgraph its own state and call it from a
       node, mapping values in and out yourself.
    2. Flatten: add the subgraph's nodes to the parent graph.   <- chosen
       One function (`add_research_stage`) still plugs it in with one line.
"""

import operator
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph


class State(TypedDict):
    texts: Annotated[list[str], operator.add]  # an append reducer
    found: Annotated[list[str], operator.add]
    plain: list[str]  # no reducer: replaced, so it is safe


def child_node(state: State) -> dict:
    return {"found": ["new"]}  # this node touches ONLY "found"


def build(as_subgraph: bool):
    if as_subgraph:
        child = StateGraph(State)
        child.add_node("child", child_node)
        child.add_edge(START, "child")
        child.add_edge("child", END)
        node = child.compile()
    else:
        node = child_node  # the same work, as a plain node

    parent = StateGraph(State)
    parent.add_node("research", node)
    parent.add_edge(START, "research")
    parent.add_edge("research", END)
    return parent.compile()


if __name__ == "__main__":
    start = {"texts": ["idea"], "found": ["earlier"], "plain": ["p"]}

    print("As a SUBGRAPH sharing state:")
    result = build(as_subgraph=True).invoke(start)
    print("   texts:", result["texts"], " <- the idea is there twice, though nothing touched it")
    print("   found:", result["found"])

    print("\nAs a plain NODE (what Archway does):")
    result = build(as_subgraph=False).invoke(start)
    print("   texts:", result["texts"])
    print("   found:", result["found"])
