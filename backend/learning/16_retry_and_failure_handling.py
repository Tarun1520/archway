"""
Lesson 16: Retries and failure handling
=======================================

What you learn here
    Networks fail. A good graph treats failure as a normal path:
      1. RETRY: ask LangGraph to re-run a node a few times with waiting in
         between (`RetryPolicy`). Good for temporary problems.
      2. CATCH AND LABEL: if it still fails, catch the error INSIDE the node
         and record "failed" in the state, so later steps can show an honest
         "not retrieved" instead of inventing a value.

How to run (from the project root)
    backend/.venv/bin/python backend/learning/16_retry_and_failure_handling.py

Where Archway uses this
    GitHub and documentation fetches (Phase 3) and the Jev call (Phase 4).
    Checkpoint 3 says "A failed fetch never produces a summary", and
    Checkpoint 4 says "With Jev unreachable, the run continues to a labeled
    partial result". Both are the pattern in PART 2.
"""

from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import RetryPolicy

attempts = {"count": 0}  # module-level counter, only so the demo can show it
always_fail = {"on": False}  # lets the demo force a permanent failure


class State(TypedDict):
    url: str
    fetch_status: str  # "ok" | "failed"
    text: str | None  # None means "not retrieved"
    error: str | None


# -----------------------------------------------------------------------------
# PART 1: a temporary failure, fixed by retrying
# -----------------------------------------------------------------------------
def flaky_fetch(state: State) -> dict:
    """Fails twice with a ConnectionError, then works."""
    attempts["count"] += 1
    if always_fail["on"] or attempts["count"] < 3:
        raise ConnectionError(f"temporary network problem (attempt {attempts['count']})")
    return {"fetch_status": "ok", "text": "README text (fixture)", "error": None}


def build_retry_graph():
    builder = StateGraph(State)
    builder.add_node(
        "fetch",
        flaky_fetch,
        # LEARNING NOTE: RetryPolicy
        #   max_attempts counts the first try too. `retry_on` limits which
        #   errors are worth retrying: a ConnectionError might go away, a
        #   bug (TypeError) will not, so we do not retry those.
        #   The waits here are tiny only so the demo is fast.
        retry_policy=RetryPolicy(
            max_attempts=3, initial_interval=0.01, backoff_factor=2.0, jitter=False,
            retry_on=ConnectionError,
        ),
    )
    builder.add_edge(START, "fetch")
    builder.add_edge("fetch", END)
    return builder.compile()


# -----------------------------------------------------------------------------
# PART 2: a permanent failure, caught and labelled
# -----------------------------------------------------------------------------
def always_failing_fetch(state: State) -> dict:
    try:
        raise ConnectionError("the server is down")
    except ConnectionError as error:
        # LEARNING NOTE: the honest-failure rule
        #   We do NOT write text="" or a made-up summary. text stays None,
        #   status says "failed", and the reason is kept for the UI.
        return {"fetch_status": "failed", "text": None, "error": str(error)}


def describe(state: State) -> dict:
    # A later step checks the status before using the text.
    if state["fetch_status"] != "ok" or state["text"] is None:
        return {"text": None}  # nothing to summarise; the UI shows "not retrieved"
    return {}


def build_catch_graph():
    builder = StateGraph(State)
    builder.add_node("fetch", always_failing_fetch)
    builder.add_node("describe", describe)
    builder.add_edge(START, "fetch")
    builder.add_edge("fetch", "describe")
    builder.add_edge("describe", END)
    return builder.compile()


if __name__ == "__main__":
    empty = {"url": "https://example.test/readme", "fetch_status": "", "text": None, "error": None}

    print("PART 1: retry succeeds on the third attempt")
    result = build_retry_graph().invoke(empty)
    print(f"  attempts used: {attempts['count']}, status: {result['fetch_status']}, text: {result['text']!r}")

    print("\nPART 1b: retries run out, so the error reaches the caller")
    attempts["count"] = 0
    always_fail["on"] = True  # make flaky_fetch fail every time
    try:
        build_retry_graph().invoke(empty)
    except ConnectionError as error:
        print(f"  raised ConnectionError after {attempts['count']} attempts: {error}")

    print("\nPART 2: failure caught inside the node and labelled")
    result = build_catch_graph().invoke(empty)
    print(f"  status: {result['fetch_status']}, text: {result['text']!r}, error: {result['error']!r}")
