"""
Node: build_roadmap. Phase 6: plans the work for the approved option version, as tasks and decision records.

What happens
    1. The call cap is checked first, like every model call (LEARNING_GUIDE.md topic 19).
    2. The planning model is shown the approved option, its reused components and their caveats
       (app/roadmap/material.py). On the retry it is also shown what the checks found.
    3. Code turns the draft into a Roadmap (app/roadmap/draft.py): ids, a real dependency order, only links to
       things that exist, spikes before the work they unblock, and ADR-1 written from the compared options.
    4. Plain-code checks (app/roadmap/checks.py) record what is still wrong, for check_prompts to act on.

Learn more: IMPLEMENTATION_GUIDE.md section 8.1.
"""

from langgraph.runtime import Runtime
from pydantic import ValidationError

from app.graph import events
from app.graph.context import RunContext
from app.graph.state import WorkflowState
from app.llm.base import LLMError
from app.options.spend import take_model_call
from app.roadmap.checks import roadmap_issues
from app.roadmap.draft import RoadmapDraft, build_roadmap as make_roadmap, parse_draft
from app.roadmap.material import material
from app.roadmap.prompts import ROADMAP_SYSTEM, roadmap_user_prompt

NODE = "build_roadmap"


async def build_roadmap(state: WorkflowState, runtime: Runtime[RunContext]) -> dict:
    emit = runtime.stream_writer
    emit(events.node_started(NODE))
    context = runtime.context
    problems = state.get("plan_issues") or []
    emit(events.activity("Plan: redrafting the roadmap to fix what the checks found" if problems else "Plan: planning the build tasks for the approved architecture"))

    if not take_model_call(state, context):
        raise LLMError(f"the cap of {context.max_llm_calls} model calls was reached before the roadmap could be planned")

    result = await context.llm.complete_json(
        step=NODE, system=ROADMAP_SYSTEM, user=roadmap_user_prompt(material(dict(state)), problems),
        schema_name="roadmap_draft", schema=RoadmapDraft.model_json_schema(),
    )
    tokens = (result.input_tokens + result.output_tokens) if result.input_tokens is not None and result.output_tokens is not None else None
    emit(events.usage(service="llm", mode=context.llm.mode, model=result.model, tokens=tokens))
    try:
        draft = parse_draft(result.data)
    except ValidationError as error:
        raise LLMError(f"the model's reply did not match the roadmap shape ({error.error_count()} problems)") from error

    roadmap, issues, notes = make_roadmap(draft, dict(state))
    issues += roadmap_issues(roadmap, dict(state))
    emit(events.activity(f"Plan: {len(roadmap.tasks)} tasks and {len(roadmap.decisions)} decision records"))
    return {
        "roadmap": roadmap.model_dump(mode="json"),
        "plan_issues": issues,
        "plan_files": [],
        "plan_notes": notes,
        "llm_calls": state["llm_calls"] + 1,
    }
