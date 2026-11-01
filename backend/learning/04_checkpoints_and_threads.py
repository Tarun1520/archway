"""
Lesson 04: Checkpointers and threads (how a graph remembers)
============================================================

What you learn here
    - A CHECKPOINTER saves a snapshot of the state after every step.
    - A THREAD is one saved conversation/run, identified by a `thread_id`.
    - With a file-based checkpointer (SQLite) the state survives a restart.

How to run (from the project root)
    backend/.venv/bin/python backend/learning/04_checkpoints_and_threads.py

Where Archway uses this
    Each Archway run is one thread. The SQLite checkpointer is what makes
    "resume saved work after a restart" (Definition of Done) possible.
"""

import operator
import tempfile
from pathlib import Path
from typing import Annotated, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph


class State(TypedDict):
    notes: Annotated[list[str], operator.add]  # grows over time


def add_note(state: State) -> dict:
    return {"notes": [f"note #{len(state['notes']) + 1}"]}


def build_graph(checkpointer):
    builder = StateGraph(State)
    builder.add_node("add_note", add_note)
    builder.add_edge(START, "add_note")
    builder.add_edge("add_note", END)
    # LEARNING NOTE: the checkpointer is plugged in at compile time.
    #   The nodes above know nothing about saving. Swapping "keep in memory"
    #   for "save to a SQLite file" changes this one argument and nothing else.
    return builder.compile(checkpointer=checkpointer)


def demo_threads() -> None:
    print("PART 1: threads keep runs separate (in-memory checkpointer)")
    graph = build_graph(InMemorySaver())

    # LEARNING NOTE: the config dictionary
    #   `thread_id` tells the checkpointer WHICH saved run to load and update.
    #   Same id = continue that run. New id = start a fresh, empty run.
    project_a = {"configurable": {"thread_id": "project-a"}}
    project_b = {"configurable": {"thread_id": "project-b"}}

    graph.invoke({"notes": []}, project_a)
    graph.invoke({"notes": []}, project_a)  # continues project-a
    graph.invoke({"notes": []}, project_b)  # separate run

    print("  project-a:", graph.get_state(project_a).values["notes"])
    print("  project-b:", graph.get_state(project_b).values["notes"])

    # Every step left a snapshot behind. Newest first.
    history = list(graph.get_state_history(project_a))
    print(f"  project-a has {len(history)} saved checkpoints; note counts:",
          [len(snapshot.values.get("notes", [])) for snapshot in history])


def demo_survives_restart() -> None:
    print("\nPART 2: a SQLite checkpointer survives a restart")
    # LEARNING NOTE: we use a temporary folder so this lesson leaves no files
    #   behind. The real app keeps its database in a configured data folder.
    with tempfile.TemporaryDirectory() as folder:
        database_file = str(Path(folder) / "checkpoints.db")
        config = {"configurable": {"thread_id": "project-a"}}

        # --- "First server process" ---
        # `with` opens the database connection and closes it at the end of
        # the block, exactly like opening and closing a file.
        with SqliteSaver.from_conn_string(database_file) as saver:
            graph = build_graph(saver)
            graph.invoke({"notes": []}, config)
            print("  before restart:", graph.get_state(config).values["notes"])

        # --- "Server restarted" ---
        # Nothing from above is reused: a new connection and a newly built
        # graph. The only thing in common is the database file.
        with SqliteSaver.from_conn_string(database_file) as saver:
            graph = build_graph(saver)
            print("  after restart :", graph.get_state(config).values["notes"])
            graph.invoke({"notes": []}, config)
            print("  one more step :", graph.get_state(config).values["notes"])


if __name__ == "__main__":
    demo_threads()
    demo_survives_restart()
