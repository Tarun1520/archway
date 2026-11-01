"""
Lesson 17: Time travel and editing saved state
==============================================

What you learn here
    Because a checkpointer saves a snapshot after every step (Lesson 04),
    you can:
      1. LIST the history of a run (`get_state_history`).
      2. EDIT the saved state from outside (`update_state`), for example
         while the run is paused at an interrupt.
      3. REPLAY from an earlier snapshot to try a different path (a "fork").

How to run (from the project root)
    backend/.venv/bin/python backend/learning/17_time_travel_and_state_edits.py

Where Archway uses this
    - Editing the brief while the run waits at `confirm_brief` (Phase 2):
      the user's edit is written into the saved state, then the run resumes.
    - Debugging: when a run produced a surprising result, list its history
      and look at the state after each node.
    - Revisions (Phase 5): trying a different option from the same earlier
      point. NOTE: Archway also keeps its own versioned records (brief v2,
      option v3) in its own tables. Checkpoint history is for resuming and
      debugging, not the user-facing version history.
"""

import operator
from typing import Annotated, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt


class State(TypedDict):
    idea: str
    brief: str
    log: Annotated[list[str], operator.add]


def draft_brief(state: State) -> dict:
    return {"brief": f"Brief for: {state['idea']}", "log": ["drafted"]}


def confirm_brief(state: State) -> dict:
    interrupt({"question": "Confirm this brief?", "brief": state["brief"]})
    return {"log": [f"confirmed: {state['brief']}"]}


def build_graph():
    builder = StateGraph(State)
    builder.add_node("draft_brief", draft_brief)
    builder.add_node("confirm_brief", confirm_brief)
    builder.add_edge(START, "draft_brief")
    builder.add_edge("draft_brief", "confirm_brief")
    builder.add_edge("confirm_brief", END)
    return builder.compile(checkpointer=InMemorySaver())


if __name__ == "__main__":
    graph = build_graph()
    config = {"configurable": {"thread_id": "run-1"}}

    graph.invoke({"idea": "notes app", "brief": "", "log": []}, config)
    print("Paused. Saved brief:", repr(graph.get_state(config).values["brief"]))

    print("\n1. History (newest first): what was saved after each step")
    for snapshot in graph.get_state_history(config):
        print(f"   next={str(snapshot.next):20} brief={snapshot.values.get('brief')!r}")

    print("\n2. Edit the saved state while the run is paused")
    # LEARNING NOTE: update_state
    #   It writes new values into the saved state as if node `as_node` had
    #   produced them, and returns a config pointing at the new snapshot.
    config_after_edit = graph.update_state(
        config, {"brief": "Brief for: notes app (edited by the user)"}, as_node="draft_brief"
    )
    print("   Saved brief now:", repr(graph.get_state(config_after_edit).values["brief"]))

    print("\n3. Resume. The confirm step sees the EDITED brief")
    # Passing Command(resume=...) continues from the interrupt.
    final = graph.invoke(Command(resume="yes"), config_after_edit)
    print("   log:", final["log"])
