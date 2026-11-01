"""
The LangGraph workflow.

    state.py      the shared memory every node reads and updates
    context.py    read-only settings for one run (the model client, the cap)
    prompts.py    the instructions sent to the language model
    events.py     small helpers for announcing progress from inside a node
    nodes/        one file per step: intake.py, clarify.py, confirm_brief.py
    build.py      wires the nodes into a graph

Phase 2 graph:

    START -> intake -> (questions?) -> clarify -> intake (once more)
                    -> (none)       -> confirm_brief -> (edit) -> confirm_brief
                                                     -> (approve) -> END

To add a step: write app/graph/nodes/<name>.py, then add one add_node line
and its edges in build.py.

Learn more: LEARNING_GUIDE.md Part B, and DEVELOPMENT_PLAN.md Phase 2.
"""
