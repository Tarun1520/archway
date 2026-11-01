"""
Lesson 18: Run-level settings (runtime context) and call caps
=============================================================

What you learn here
    Two kinds of data travel through a graph run:
      STATE   - what the workflow is producing (changes as nodes run).
      CONTEXT - settings for THIS run that nodes only read, never change
                (for example "at most 3 model calls").
    Keeping them apart stops settings being mixed into results.

    You also see the call-cap pattern: a COUNTER in state, a LIMIT in
    context, and a node that stops spending when the counter reaches the limit.

How to run (from the project root)
    backend/.venv/bin/python backend/learning/18_runtime_context_and_call_caps.py

Where Archway uses this
    Section 5.3 of IMPLEMENTATION_GUIDE.md: "LLM calls per run" and "Jev calls
    per run" are required limits, and "when a cap is reached, stop making
    that class of call and return a partial result with a visible
    explanation". This is that rule as code.
"""

from dataclasses import dataclass
from typing import Annotated, Literal, TypedDict
import operator

from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from langgraph.types import Command


# LEARNING NOTE: context is a plain dataclass.
#   It is passed when you START the run: graph.invoke(..., context=RunLimits(...)).
@dataclass
class RunLimits:
    max_llm_calls: int


class State(TypedDict):
    questions_left: list[str]
    answers: Annotated[list[str], operator.add]
    llm_calls: int  # the counter
    outcome: str


def answer_next(state: State, runtime: Runtime[RunLimits]) -> Command[Literal["answer_next", "finish"]]:
    """Answer one question per visit, unless the cap has been reached."""
    limit = runtime.context.max_llm_calls  # read the setting for THIS run

    if not state["questions_left"]:
        return Command(update={"outcome": "full: every question answered"}, goto="finish")

    if state["llm_calls"] >= limit:
        # Cap reached: stop calling, and say so in the result.
        left = len(state["questions_left"])
        note = f"partial: cap of {limit} model calls reached, {left} question(s) unanswered"
        return Command(update={"outcome": note}, goto="finish")

    question, *rest = state["questions_left"]
    # FIXTURE: a fake "model call" stands in for a real, paid one.
    return Command(
        update={
            "answers": [f"answer to {question!r}"],
            "questions_left": rest,
            "llm_calls": state["llm_calls"] + 1,
        },
        goto="answer_next",
    )


def finish(state: State) -> dict:
    return {}


def build_graph():
    # context_schema tells LangGraph what type of context this graph expects.
    builder = StateGraph(State, context_schema=RunLimits)
    builder.add_node("answer_next", answer_next)
    builder.add_node("finish", finish)
    builder.add_edge(START, "answer_next")
    builder.add_edge("finish", END)
    return builder.compile()


if __name__ == "__main__":
    graph = build_graph()
    start = {"questions_left": ["q1", "q2", "q3", "q4"], "answers": [], "llm_calls": 0, "outcome": ""}

    for cap in (10, 2):
        result = graph.invoke(start, context=RunLimits(max_llm_calls=cap))
        print(f"cap = {cap:2}: {result['llm_calls']} calls made | {result['outcome']}")
        print(f"          answers: {result['answers']}")
