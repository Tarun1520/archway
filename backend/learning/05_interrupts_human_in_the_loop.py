"""
Lesson 05: Interrupts (pausing the graph to ask a human)
========================================================

What you learn here
    - `interrupt(question)` pauses the run INSIDE a node and hands a question
      to whoever started the run.
    - `Command(resume=answer)` continues the run; the answer becomes the
      return value of that same `interrupt(...)` call.
    - Because the pause is saved by the checkpointer, the answer can arrive
      minutes later, even after the server was restarted.

How to run (from the project root)
    backend/.venv/bin/python backend/learning/05_interrupts_human_in_the_loop.py

Where Archway uses this
    Four steps wait for the user: clarify, confirm_brief, select_or_revise and
    approve_version. This lesson is a small `confirm_brief`.
"""

import tempfile
from pathlib import Path
from typing import TypedDict

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt


class State(TypedDict):
    idea: str
    brief: str
    confirmed: bool


def draft_brief(state: State) -> dict:
    return {"brief": f"Problem: {state['idea']}. Users: unknown."}


def confirm_brief(state: State) -> dict:
    # LEARNING NOTE: this line runs TWICE. Watch the output.
    #   When the run is resumed, LangGraph starts this node again from its
    #   first line. So anything placed before interrupt() must be safe to
    #   repeat (never "charge the card" or "send the email" up here).
    print("    [confirm_brief node started]")

    # The run stops here. The dictionary is the question shown to the user.
    # It must be simple data (text, numbers, lists, dicts) so it can be saved.
    answer = interrupt({"question": "Is this brief correct?", "brief": state["brief"]})

    # We only get here after a resume. `answer` is whatever was passed to
    # Command(resume=...). The user may have edited the brief.
    return {"confirmed": answer["approved"], "brief": answer.get("edited_brief", state["brief"])}


def start_research(state: State) -> dict:
    print("    [research would start here, using the confirmed brief]")
    return {}


def build_graph(checkpointer):
    builder = StateGraph(State)
    builder.add_node("draft_brief", draft_brief)
    builder.add_node("confirm_brief", confirm_brief)
    builder.add_node("start_research", start_research)
    builder.add_edge(START, "draft_brief")
    builder.add_edge("draft_brief", "confirm_brief")
    builder.add_edge("confirm_brief", "start_research")
    builder.add_edge("start_research", END)
    # LEARNING NOTE: interrupts REQUIRE a checkpointer. Pausing means
    #   "save everything and stop", and the checkpointer does the saving.
    return builder.compile(checkpointer=checkpointer)


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as folder:
        database_file = str(Path(folder) / "checkpoints.db")
        config = {"configurable": {"thread_id": "run-1"}}

        print("STEP 1: start the run. It pauses at confirm_brief.")
        with SqliteSaver.from_conn_string(database_file) as saver:
            graph = build_graph(saver)
            result = graph.invoke({"idea": "a notes app", "confirmed": False}, config)

            # The paused run reports its question under the "__interrupt__" key.
            question = result["__interrupt__"][0].value
            print("    question for the user:", question)
            # .next tells you which node is waiting.
            print("    waiting at node      :", graph.get_state(config).next)

        print("\nSTEP 2: the server 'restarts'. Nothing is kept in memory.")

        print("\nSTEP 3: the user answers. Resume the SAME thread_id.")
        with SqliteSaver.from_conn_string(database_file) as saver:
            graph = build_graph(saver)
            answer = {"approved": True, "edited_brief": "Problem: a notes app. Users: students."}
            final = graph.invoke(Command(resume=answer), config)

            print("    confirmed:", final["confirmed"])
            print("    brief    :", final["brief"])
            print("    waiting at node:", graph.get_state(config).next, "(empty = finished)")
