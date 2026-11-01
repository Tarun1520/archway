"""
The options stage (Phase 5): turning the researched, checked components into architecture options.

One file per concern:

    material.py     what the model is shown: the brief, the capabilities, the reusable components with
                    their decisions (and which engine, e.g. Laya, made them), and what may NOT be reused
    draft.py        the shape the model fills in, and the code that turns it into real, versioned options
    mermaid_safe.py makes a diagram safe to draw (no scripts, no links)
    checks.py       the review gate: plain-Python checks first, then what the reviewing model found
    prompts.py      the instructions for the drafting and reviewing models
    versions.py     which version of each option is current, which passed review, which is approved

The graph nodes that use these are in app/graph/nodes/ (draft_options, review_options,
select_or_revise, approve_version).
"""
