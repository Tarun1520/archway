"""
Lesson 26: A team of agents (a lead, specialists, and a team channel)
=====================================================================

What you learn here
    How Archway's research team is put together, in miniature and offline:

    1. A LEAD node decides who works next, and returns a `Command`:
         Command(goto="analyst")                       hand off to one agent
         Command(goto=[Send("scout", {...}), ...])     several agents in parallel
         Command(goto=END)                             the work is done
    2. Every SPECIALIST reports back to the lead (an edge back to it).
       When several work in parallel, the lead runs once, after all finish.
    3. Each specialist runs its OWN small graph with PRIVATE state (its own
       conversation), invoked from its node. Private state is what avoids the
       doubling trap of Lesson 24.
    4. The agents "talk" through a shared list, `messages`: tasks from the
       lead and reports back. That list is the team channel.

    The "thinking" here is scripted (no model), so it runs instantly and the
    same every time. In Archway, each decision is a model choosing a tool.

How to run (from the project root)
    backend/.venv/bin/python backend/learning/26_agent_team.py

Where Archway uses this
    backend/app/agents/ (one file per agent) and backend/app/graph/research_team.py.
"""

import asyncio
import operator
from typing import Annotated, Any, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, Send


# --- The team's shared board ------------------------------------------------------------
class Board(TypedDict):
    capabilities: list[str]
    findings: Annotated[list[str], operator.add]  # several scouts add at the same time
    messages: Annotated[list[str], operator.add]  # the team channel
    lead_turns: int


# --- One specialist's PRIVATE loop -----------------------------------------------------------
class ScoutState(TypedDict):
    capability: str
    notes: Annotated[list[str], operator.add]  # only this scout sees these


def scout_think(state: ScoutState) -> dict:
    # In Archway this is "ask the model which tool to use, then run the tool".
    return {"notes": [f"searched for '{state['capability']}' options", f"verified 2 options for '{state['capability']}'"]}


scout_loop = StateGraph(ScoutState)
scout_loop.add_node("think", scout_think)
scout_loop.add_edge(START, "think")
scout_loop.add_edge("think", END)
SCOUT_LOOP = scout_loop.compile()


# --- The nodes of the main graph ----------------------------------------------------------
def lead(state: Board) -> Command:
    turns = state["lead_turns"] + 1
    if not state["capabilities"]:
        return Command(goto="analyst", update={"lead_turns": turns, "messages": ["lead -> analyst: list the capabilities"]})
    if not state["findings"]:
        sends = [Send("scout", {"capability": c}) for c in state["capabilities"]]
        return Command(goto=sends, update={"lead_turns": turns, "messages": ["lead -> scouts: one per capability, in parallel"]})
    return Command(goto=END, update={"lead_turns": turns, "messages": ["lead -> team: research finished"]})


def analyst(state: Board) -> dict:
    return {"capabilities": ["parsing", "search", "sync"], "messages": ["analyst -> lead: 3 capabilities"]}


async def scout(task: dict[str, Any], config: RunnableConfig) -> dict:
    # Run this scout's own loop with its own state; read only its result out.
    result = await SCOUT_LOOP.ainvoke({"capability": task["capability"], "notes": []}, config)
    return {
        "findings": [f"{task['capability']}: {result['notes'][-1]}"],
        "messages": [f"scout({task['capability']}) -> lead: {result['notes'][-1]}"],
    }


def build_team():
    builder = StateGraph(Board)
    builder.add_node("lead", lead, destinations=("analyst", "scout", "__end__"))
    builder.add_node("analyst", analyst)
    builder.add_node("scout", scout)
    builder.add_edge(START, "lead")
    builder.add_edge("analyst", "lead")
    builder.add_edge("scout", "lead")  # all parallel scouts report back; the lead runs once after them
    return builder.compile()


async def main() -> None:
    final = await build_team().ainvoke({"capabilities": [], "findings": [], "messages": [], "lead_turns": 0})
    print("The team channel, in order:")
    for line in final["messages"]:
        print("   ", line)
    print("\nFindings:", final["findings"])
    print("Lead decisions:", final["lead_turns"])


if __name__ == "__main__":
    asyncio.run(main())
