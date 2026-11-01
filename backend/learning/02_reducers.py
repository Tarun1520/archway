"""
Lesson 02: Reducers (how updates are merged into state)
=======================================================

What you learn here
    When a node returns {"key": value}, LangGraph has to decide what to do
    with the value that was already stored under "key". The rule it uses for
    that key is called a REDUCER.
      - No reducer  -> the new value REPLACES the old one.
      - With reducer -> the reducer COMBINES old and new (for example, append).

How to run (from the project root)
    backend/.venv/bin/python backend/learning/02_reducers.py

Where Archway uses this
    Lists that grow during a run (candidates, evidence, receipts, messages)
    need an "append" reducer. Single values (the current brief, the selected
    option) use the default "replace" behaviour.
"""

import operator
from typing import Annotated, TypedDict

from langgraph.errors import InvalidUpdateError
from langgraph.graph import END, START, StateGraph


# LEARNING NOTE: how to attach a reducer
#   Annotated[<type>, <reducer>] means "this key has this type, and here is
#   the function to merge updates with". operator.add is Python's "+".
#   For lists, old + new joins the two lists, which is an append.
class State(TypedDict):
    status: str  # no reducer: last write wins
    activity: Annotated[list[str], operator.add]  # reducer: updates are appended


def search_github(state: State) -> dict:
    return {"status": "searching", "activity": ["GitHub: 14 candidates retrieved"]}


def fetch_docs(state: State) -> dict:
    return {"activity": ["Docs: 3 pages fetched"]}


def finish(state: State) -> dict:
    return {"status": "done", "activity": ["Research finished"]}


def build_graph():
    builder = StateGraph(State)
    builder.add_node("search_github", search_github)
    builder.add_node("fetch_docs", fetch_docs)
    builder.add_node("finish", finish)

    # LEARNING NOTE: running nodes in parallel ("fan-out")
    #   Two edges leaving START means both nodes run in the same step.
    #   Both write to "activity". That is safe ONLY because "activity" has a
    #   reducer that knows how to combine two updates.
    builder.add_edge(START, "search_github")
    builder.add_edge(START, "fetch_docs")

    # "finish" waits until BOTH parallel nodes are done ("fan-in").
    builder.add_edge(["search_github", "fetch_docs"], "finish")
    builder.add_edge("finish", END)
    return builder.compile()


# -----------------------------------------------------------------------------
# What goes wrong without a reducer
# -----------------------------------------------------------------------------
class BrokenState(TypedDict):
    activity: list[str]  # no reducer this time


def build_broken_graph():
    builder = StateGraph(BrokenState)
    builder.add_node("a", lambda state: {"activity": ["from a"]})
    builder.add_node("b", lambda state: {"activity": ["from b"]})
    builder.add_edge(START, "a")
    builder.add_edge(START, "b")
    builder.add_edge(["a", "b"], END)
    return builder.compile()


if __name__ == "__main__":
    result = build_graph().invoke({"status": "new", "activity": ["Run started"]})
    print("status  :", result["status"], "(replaced each time; last write wins)")
    print("activity:")
    for line in result["activity"]:
        print("   -", line)

    print("\nNow two parallel nodes write the same key WITHOUT a reducer:")
    try:
        build_broken_graph().invoke({"activity": []})
    except InvalidUpdateError as error:
        # LangGraph refuses to guess which of the two writes should win.
        print("   LangGraph raised InvalidUpdateError:")
        print("  ", str(error).splitlines()[0])
