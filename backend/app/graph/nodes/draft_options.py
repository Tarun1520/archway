"""
Node: draft_options. Phase 5: proposes architecture options from the researched, checked components.

Three modes (chosen from the state, not by the model)
    new      no options yet: draft one to three from scratch (a single option, or "no recommendation", is fine)
    revise   the person asked for a change to one option (state["revision"]): draft the NEXT VERSION of it,
             with a note of what changed and what else it touches
    fix      some options failed the review gate (state["option_feedback"]): redraft only those, told what failed

What the code does around the model (app/options/draft.py)
    ids and versions, copying a reused repository's name from the researched facts, dropping a reuse that names
    nothing real (reported as a blocking issue), keeping only real evidence ids, a safe diagram, all eight
    comparison dimensions, "unknown" for a requirement the model skipped.

The call cap is checked first, like every model call (LEARNING_GUIDE.md topic 19).

Learn more: IMPLEMENTATION_GUIDE.md section 7.
"""

from langgraph.runtime import Runtime
from pydantic import ValidationError

from app.graph import events
from app.graph.context import RunContext
from app.graph.state import WorkflowState
from app.llm.base import LLMError
from app.options.draft import OptionsDraft, build_options, parse_draft
from app.options.material import material
from app.options.prompts import DRAFT_SYSTEM, draft_user_prompt
from app.options.spend import take_model_call
from app.options.versions import find, presented

NODE = "draft_options"


async def draft_options(state: WorkflowState, runtime: Runtime[RunContext]) -> dict:
    emit = runtime.stream_writer
    emit(events.node_started(NODE))
    context = runtime.context

    revision = state.get("revision")
    feedback = state.get("option_feedback") or {}
    options = state.get("options", [])
    shown = {o["id"]: o for o in presented(options)}

    previous = failed = None
    request = None
    if revision and revision.get("option_id"):
        mode, keys = "revise", [revision["option_id"]]
        previous, request = shown.get(keys[0]) or find(options, keys[0]), revision["request"]
        emit(events.activity(f"Options: drafting a new version of {keys[0]} for your change request"))
    elif feedback:
        mode, keys = "fix", list(feedback)
        failed = [{**(find(options, key) or {}), "issues_to_fix": feedback[key]} for key in keys]
        emit(events.activity(f"Options: redrafting {', '.join(keys)} to fix what the review found"))
    else:
        mode, keys = "new", []
        request = (revision or {}).get("request")  # extra guidance for a fresh set, if any
        emit(events.activity("Options: drafting architecture options from the checked components"))

    if not take_model_call(state, context):
        raise LLMError(f"the cap of {context.max_llm_calls} model calls was reached before the options could be drafted")

    prompt = draft_user_prompt(material(state), mode=mode, previous=previous, request=request, failed=failed)
    if mode == "new" and request:
        prompt += f"\n\n<extra_guidance_from_the_person>\n{request.strip()}\n</extra_guidance_from_the_person>"
    result = await context.llm.complete_json(
        step=NODE, system=DRAFT_SYSTEM, user=prompt, schema_name="options_draft", schema=OptionsDraft.model_json_schema(),
    )
    tokens = (result.input_tokens + result.output_tokens) if result.input_tokens is not None and result.output_tokens is not None else None
    emit(events.usage(service="llm", mode=context.llm.mode, model=result.model, tokens=tokens))
    try:
        draft = parse_draft(result.data)
    except ValidationError as error:
        raise LLMError(f"the model's reply did not match the options shape ({error.error_count()} problems)") from error

    built, problems, notes = build_options(draft, dict(state), mode=mode, keys=keys)
    no_recommendation = mode == "new" and not built
    if no_recommendation:
        reason = (draft.no_recommendation_reason or "").strip() or "the model proposed no option and gave no reason"
        notes.append(f"No recommendation: {reason}")
        emit(events.activity("Options: no option can be recommended from the evidence found"))
    elif mode in ("revise", "fix") and not built:
        notes.append(f"The model returned no new version for {', '.join(keys)}.")

    emit(events.activity(f"Options: {len(built)} option version(s) drafted"))
    return {
        "options": [*options, *built],
        "option_problems": {**(state.get("option_problems") or {}), **problems},
        "option_feedback": {},
        "revision": None,
        "option_retries": (state.get("option_retries", 0) + 1) if mode == "fix" else 0,
        "selected_option_id": None,
        "approved_option": None,
        "no_recommendation": no_recommendation,
        "options_notes": notes,
        "llm_calls": state["llm_calls"] + 1,
    }
