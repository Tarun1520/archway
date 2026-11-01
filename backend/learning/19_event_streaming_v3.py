"""
Lesson 19: The newer event-streaming API (`stream_events`, version "v3")
========================================================================

What you learn here
    LangGraph 1.2 added a second way to watch a run. Instead of looping over
    raw events and sorting them with `if event["type"] == ...`, you get a
    RUN OBJECT with ready-made views:
        run.values      - the full state after each step
        run.interrupted - did the run pause for a human?
        run.interrupts  - the questions it paused with
        run.output      - the final result

    IMPORTANT: when this lesson was written, LangChain's own warning said
    "The v3 streaming protocol on Pregel is experimental". This lesson
    silences that warning so the output is readable, but treat it as unstable.

How to run (from the project root)
    backend/.venv/bin/python backend/learning/19_event_streaming_v3.py

Where Archway uses this
    Nothing yet. The plan (IMPLEMENTATION_GUIDE.md section 2.1) is to decide in
    Phase 2, before writing the run-events API. Lesson 06 and 12's
    `stream(..., version="v2")` is stable and is the safe default; this
    lesson exists so you can compare the two and choose with eyes open.
"""

import warnings
from typing import TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

# Hide LangChain's "experimental" beta warning so the lesson output is clean.
warnings.filterwarnings("ignore")


class State(TypedDict):
    n: int


def add_one(state: State) -> dict:
    return {"n": state["n"] + 1}


def ask_user(state: State) -> dict:
    approved = interrupt("Add ten more?")
    return {"n": state["n"] + (10 if approved else 0)}


def build_graph():
    builder = StateGraph(State)
    builder.add_node("add_one", add_one)
    builder.add_node("ask_user", ask_user)
    builder.add_edge(START, "add_one")
    builder.add_edge("add_one", "ask_user")
    builder.add_edge("ask_user", END)
    return builder.compile(checkpointer=InMemorySaver())


if __name__ == "__main__":
    graph = build_graph()
    config = {"configurable": {"thread_id": "run-1"}}

    print("First pass: the run pauses at ask_user")
    run = graph.stream_events({"n": 0}, config, version="v3")
    for state_after_step in run.values:
        print("   state:", state_after_step)
    print("   interrupted:", run.interrupted)
    print("   question   :", [item.value for item in run.interrupts])

    print("\nResume with 'yes'")
    resumed = graph.stream_events(Command(resume=True), config, version="v3")
    print("   output     :", resumed.output)
    print("   interrupted:", resumed.interrupted)
