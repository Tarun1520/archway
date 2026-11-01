"""
Lesson 06: Streaming (watching a run while it happens)
======================================================

What you learn here
    `.invoke()` gives you only the final answer. `.stream()` gives you events
    WHILE the graph runs. You choose what kind of events with `stream_mode`:
      "updates" - after each node: which node ran and what it changed
      "values"  - after each step: the whole state
      "custom"  - anything a node chooses to announce while it is working

How to run (from the project root)
    backend/.venv/bin/python backend/learning/06_streaming_progress.py

Where Archway uses this
    The live workflow view lights up nodes from "updates" events. The activity
    feed ("GitHub: 14 candidates retrieved") comes from "custom" events. The
    backend forwards both to the browser as server-sent events (Lesson 10).
"""

import json
from typing import TypedDict

from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph


class State(TypedDict):
    query: str
    candidates: int
    shortlisted: int


def github_search(state: State) -> dict:
    # LEARNING NOTE: custom events
    #   get_stream_writer() returns a function. Whatever you pass to it is
    #   sent to the listener immediately, before this node has finished.
    #   Use it for honest progress messages about work that really happened.
    write = get_stream_writer()
    write({"message": f"GitHub: searching for '{state['query']}'"})
    found = 14  # pretend result
    write({"message": f"GitHub: {found} candidates retrieved"})
    return {"candidates": found}


def shortlist(state: State) -> dict:
    return {"shortlisted": min(state["candidates"], 5)}


def build_graph():
    builder = StateGraph(State)
    builder.add_node("github_search", github_search)
    builder.add_node("shortlist", shortlist)
    builder.add_edge(START, "github_search")
    builder.add_edge("github_search", "shortlist")
    builder.add_edge("shortlist", END)
    return builder.compile()


def to_sse(event_name: str, data: dict) -> str:
    """Show what one event looks like in the server-sent events text format."""
    return f"event: {event_name}\ndata: {json.dumps(data)}\n"


if __name__ == "__main__":
    graph = build_graph()
    inputs = {"query": "markdown notes", "candidates": 0, "shortlisted": 0}

    print("PART 1: two stream modes at once")
    # LEARNING NOTE: version="v2"
    #   With version="v2" every event has the same shape:
    #     {"type": <stream mode>, "ns": <subgraph path>, "data": <payload>}
    #   so one `if` on "type" is enough to tell the kinds apart.
    for event in graph.stream(inputs, stream_mode=["updates", "custom"], version="v2"):
        if event["type"] == "custom":
            print("  progress :", event["data"]["message"])
        elif event["type"] == "updates":
            for node_name, changes in event["data"].items():
                print(f"  node done: {node_name} changed {changes}")

    print("\nPART 2: the same events, as the browser would receive them (SSE)")
    for event in graph.stream(inputs, stream_mode=["updates", "custom"], version="v2"):
        print(to_sse(event["type"], event["data"]))

    print("PART 3: 'values' mode shows the whole state after each step")
    for event in graph.stream(inputs, stream_mode="values", version="v2"):
        print("  state:", event["data"])
