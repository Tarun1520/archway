"""
DEMO events for the live-progress stream.

What this file does
    Holds a short, made-up sequence of events so the frontend can be built
    and tested before the real workflow exists.

IMPORTANT: this is demo data
    None of this happened. Every event carries "demo": true, and the stream
    starts with a notice saying so, so the UI can label it (working
    agreement: "Mark demo data").

How it plugs in
    app/api/demo_events.py streams this list to the browser.
    In Phase 2 the real events come from the LangGraph run instead
    (LEARNING_GUIDE.md topics 12 and 34), and this file is only used by the
    demo endpoint.
"""

# Each item is (event name, data). The names match what the real workflow
# will send later, so the frontend code written now keeps working.
DEMO_EVENT_SCRIPT: list[tuple[str, dict]] = [
    ("demo_notice", {"message": "Demo stream: these events are sample data, not a real run."}),
    ("node_started", {"node": "intake"}),
    ("activity", {"message": "Intake: reading the idea"}),
    ("node_finished", {"node": "intake"}),
    ("node_waiting", {"node": "confirm_brief", "message": "Waiting for you to confirm the brief"}),
    ("node_finished", {"node": "confirm_brief"}),
    ("node_started", {"node": "github_search"}),
    ("activity", {"message": "GitHub: 14 candidates retrieved"}),
    ("node_finished", {"node": "github_search"}),
    ("node_started", {"node": "eligibility_gate"}),
    ("activity", {"message": "License review required: example/md-vault"}),
    ("node_finished", {"node": "eligibility_gate"}),
    ("stream_finished", {"message": "End of demo stream."}),
]


def demo_events() -> list[tuple[str, dict]]:
    """The script, with every event marked as demo data."""
    return [(name, {**data, "demo": True}) for name, data in DEMO_EVENT_SCRIPT]
