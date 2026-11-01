"""
Lesson 15: Send (fan out over a list whose size you do not know in advance)
===========================================================================

What you learn here
    In Lesson 02 you drew two parallel edges by hand. That only works when you
    know the number of branches while writing the code. `Send` handles the
    other case: "run this node once for EACH item in a list", where the list
    length is only known at run time. This pattern is called map-reduce:
      map    = one task per item, all in the same step
      reduce = a reducer on the state key collects every task's answer

How to run (from the project root)
    backend/.venv/bin/python backend/learning/15_send_fan_out.py

Where Archway uses this
    The `jev_decisions` step asks separate, bounded questions for each
    candidate repository and each requirement. That is one task per
    (candidate, requirement) pair, so the count depends on the data. The
    shortlist cap (5 inspected repositories) is applied BEFORE fanning out,
    which keeps the number of paid calls bounded.
"""

import operator
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

MAX_INSPECTED = 5  # the cap: never fan out over more than this many


class State(TypedDict):
    candidates: list[str]
    # Reducer: each parallel task adds its own list; LangGraph concatenates.
    verdicts: Annotated[list[dict], operator.add]
    summary: str


def fan_out(state: State) -> list[Send]:
    """Create one Send per candidate, after applying the cap.

    LEARNING NOTE: what is a Send?
      Send("node_name", payload) means "run node_name with THIS payload".
      The payload does not have to look like the main State; it is whatever
      the target node needs. Here it is just {"candidate": "..."}.
    """
    capped = state["candidates"][:MAX_INSPECTED]
    return [Send("judge_candidate", {"candidate": name}) for name in capped]


def judge_candidate(payload: dict) -> dict:
    """Runs once per Send. FIXTURE LOGIC: a fake rule stands in for Jev."""
    name = payload["candidate"]
    verdict = "needs review" if name.endswith("-nolicense") else "fits"
    return {"verdicts": [{"candidate": name, "verdict": verdict}]}


def summarise(state: State) -> dict:
    reviewed = [v["candidate"] for v in state["verdicts"] if v["verdict"] == "needs review"]
    return {"summary": f"{len(state['verdicts'])} judged; needs review: {sorted(reviewed)}"}


def build_graph():
    builder = StateGraph(State)
    builder.add_node("judge_candidate", judge_candidate)
    builder.add_node("summarise", summarise)

    # The router returns a list of Send objects instead of a node name.
    # The third argument lists which nodes it may send to (for drawing).
    builder.add_conditional_edges(START, fan_out, ["judge_candidate"])
    builder.add_edge("judge_candidate", "summarise")  # waits for ALL tasks
    builder.add_edge("summarise", END)
    return builder.compile()


if __name__ == "__main__":
    graph = build_graph()

    small = graph.invoke({"candidates": ["a", "b-nolicense", "c"], "verdicts": [], "summary": ""})
    print("3 candidates:")
    print("  ", small["summary"])

    many = [f"repo-{n}" for n in range(12)] + ["z-nolicense"]
    capped = graph.invoke({"candidates": many, "verdicts": [], "summary": ""})
    print("\n13 candidates, but the cap is", MAX_INSPECTED, "so only that many are judged:")
    print("  ", capped["summary"])
    print("   verdict count:", len(capped["verdicts"]))
