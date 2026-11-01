"""
Lesson 12: The async graph (how the real backend will run LangGraph)
====================================================================

What you learn here
    Lessons 01-06 used the simple "sync" calls (invoke, stream). A FastAPI
    server is async, so the real backend uses the async twins:
      invoke            -> ainvoke
      stream            -> astream
      SqliteSaver       -> AsyncSqliteSaver
      def node(...)     -> async def node(...)
    Everything else you learned stays the same.

    This lesson combines the pieces: an async graph, saved to SQLite, that
    streams progress, pauses for the user, and resumes.

How to run (from the project root)
    backend/.venv/bin/python backend/learning/12_async_graph_with_sqlite.py

Where Archway uses this
    This is the shape of backend/app/graph/ plus the run-events API route.
"""

import asyncio
import tempfile
from pathlib import Path
from typing import TypedDict

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt


class State(TypedDict):
    idea: str
    brief: str
    confirmed: bool


async def intake(state: State) -> dict:
    write = get_stream_writer()
    write({"message": "Intake: extracting a brief from the idea"})
    await asyncio.sleep(0.05)  # stands in for a slow model call
    return {"brief": f"Problem: {state['idea']}"}


async def confirm_brief(state: State) -> dict:
    answer = interrupt({"question": "Is this brief correct?", "brief": state["brief"]})
    return {"confirmed": bool(answer["approved"])}


def build_graph(checkpointer):
    builder = StateGraph(State)
    builder.add_node("intake", intake)
    builder.add_node("confirm_brief", confirm_brief)
    builder.add_edge(START, "intake")
    builder.add_edge("intake", "confirm_brief")
    builder.add_edge("confirm_brief", END)
    return builder.compile(checkpointer=checkpointer)


async def print_events(graph, graph_input, config) -> None:
    """Run (or resume) the graph and print each event as it arrives."""
    async for event in graph.astream(
        graph_input, config, stream_mode=["updates", "custom"], version="v2"
    ):
        if event["type"] == "custom":
            print("    activity :", event["data"]["message"])
            continue
        for node_name, changes in event["data"].items():
            if node_name == "__interrupt__":
                # A pause shows up in the stream as a special "node".
                print("    PAUSED   :", changes[0].value["question"])
            else:
                print(f"    node done: {node_name} -> {changes}")


async def main() -> None:
    with tempfile.TemporaryDirectory() as folder:
        database_file = str(Path(folder) / "checkpoints.db")
        config = {"configurable": {"thread_id": "run-1"}}

        # `async with` is the async form of `with`: open, use, always close.
        async with AsyncSqliteSaver.from_conn_string(database_file) as saver:
            graph = build_graph(saver)

            print("Start the run:")
            await print_events(graph, {"idea": "a notes app", "confirmed": False}, config)

            snapshot = await graph.aget_state(config)
            print("    waiting at:", snapshot.next)

            print("\nThe user approves. Resume the run:")
            await print_events(graph, Command(resume={"approved": True}), config)

            snapshot = await graph.aget_state(config)
            print("    final state:", snapshot.values)


if __name__ == "__main__":
    asyncio.run(main())
