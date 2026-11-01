"""
Announcing progress from inside a node.

What this file does
    Three tiny helpers that build the dictionaries nodes send through
    LangGraph's "custom" stream (LEARNING_GUIDE.md topic 12). Using helpers
    keeps the event names spelled the same way everywhere.

The honesty rule
    A node only announces something that has actually happened. The UI shows
    these events as they are; there are no timers or invented progress.

How it plugs in
    Nodes call e.g.  runtime.stream_writer(activity("Brief drafted")).
    app/workflow/service.py receives them, saves them, and the browser reads
    them from the saved events.
"""

from typing import Any


def node_started(node: str) -> dict[str, Any]:
    return {"event": "node_started", "node": node}


def activity(message: str) -> dict[str, Any]:
    """One line for the activity feed."""
    return {"event": "activity", "message": message}


def usage(*, service: str, mode: str, model: str | None, tokens: int | None) -> dict[str, Any]:
    """One call was made to an outside service."""
    return {"event": "usage", "service": service, "mode": mode, "model": model, "tokens": tokens}


def rate_limited(*, service: str, wait_seconds: float, will_wait: bool) -> dict[str, Any]:
    """A service said to slow down, and whether the run is waiting it out."""
    return {"event": "rate_limited", "service": service, "wait_seconds": round(wait_seconds), "will_wait": will_wait}


def agent_action(*, agent: str, tool: str, ok: bool, about: str | None = None, count: int | None = None) -> dict[str, Any]:
    """An agent used one of its tools. `about` and `count` say what on, in a few
    words (app/agents/action_subject.py); the studio shows them as plain text."""
    return {"event": "agent_action", "agent": agent, "tool": tool, "ok": ok, "about": about, "count": count}


# The places research can look. The studio shows only the ones a run really used.
SOURCES = ("github", "npm", "pypi", "hacker_news", "stack_overflow", "brave")


def source_used(source: str, results: int) -> dict[str, Any]:
    """A tool looked something up in one outside source (`source` is one of SOURCES), and got `results` back.

    Saved with the run, so the studio can say truthfully WHERE this run looked.
    """
    return {"event": "source_used", "source": source, "results": results}
