"""
Node: review_options. Phase 5: the review gate between a draft and the person (IMPLEMENTATION_GUIDE.md 7.3).

Order
    1. Plain-Python rules on every newly drafted option (app/options/checks.py): every reused repository is
       `eligible`, nothing is reused without naming a real component, pros AND cons, and so on.
    2. One model call to review all of them together: broken stated constraints, contradictions, claims the cited
       evidence does not support (these become VALIDATION TASKS, not rejections).
       If the call cap is reached or the model fails, the options are judged by the rules alone and the review
       says so (`llm_checked: false`).
    3. An option with a blocking issue goes back to `draft_options` with what was wrong, at most MAX_REVIEW_RETRIES
       times. After that it is NOT presented, and the notes say why. If nothing passes, the person is told
       "no recommendation" with the reasons.

Where it goes next: `draft_options` (a retry) or `select_or_revise` (the person decides).
"""

from typing import Literal

from langgraph.runtime import Runtime
from langgraph.types import Command

from app.graph import events
from app.graph.context import RunContext
from app.graph.state import WorkflowState
from app.llm.base import LLMError
from app.options.checks import ModelReview, apply_review, feedback_for, rule_issues
from app.options.material import brief_view, evidence_excerpts
from app.options.prompts import REVIEW_SYSTEM, review_user_prompt
from app.options.spend import calls_left, take_model_call
from app.options.versions import unreviewed

NODE = "review_options"
MAX_REVIEW_RETRIES = 2  # redrafts after a failed review (IMPLEMENTATION_GUIDE.md 5.3)
REVIEW_FIELDS = (
    "id", "version", "name", "trade_off", "summary", "components", "requirement_coverage", "integration_boundaries",
    "data_flow", "storage_model", "deployment", "security_privacy", "risks", "evidence_ids", "pros", "cons",
)


async def review_options(state: WorkflowState, runtime: Runtime[RunContext]) -> Command[Literal["draft_options", "select_or_revise"]]:
    emit = runtime.stream_writer
    emit(events.node_started(NODE))
    context = runtime.context
    options = list(state.get("options", []))
    pending = unreviewed(options)
    if not pending:
        return Command(goto="select_or_revise")

    notes: list[str] = []
    problems = state.get("option_problems") or {}
    rules = {f"{o['id']}@{o['version']}": rule_issues(o, dict(state), problems.get(f"{o['id']}@{o['version']}", [])) for o in pending}

    # --- the model's check (one call for all the new options) -----------------------
    model_issues = None
    llm_calls = state["llm_calls"]
    if not take_model_call(dict(state), context):
        notes.append(f"Model call cap reached: the options were checked by rules only ({', '.join(o['id'] for o in pending)}).")
    else:
        cited = {e for o in pending for e in o.get("evidence_ids", [])}
        emit(events.activity(f"Options: reviewing {len(pending)} option(s) against the brief and the evidence"))
        try:
            result = await context.llm.complete_json(
                step=NODE, system=REVIEW_SYSTEM,
                user=review_user_prompt(
                    brief_view(state.get("brief") or {}), [{k: o.get(k) for k in REVIEW_FIELDS} for o in pending],
                    evidence_excerpts(dict(state), cited),
                ),
                schema_name="options_review", schema=ModelReview.model_json_schema(),
            )
            llm_calls += 1  # (the allowance was already spent by take_model_call)
            tokens = (result.input_tokens + result.output_tokens) if result.input_tokens is not None and result.output_tokens is not None else None
            emit(events.usage(service="llm", mode=context.llm.mode, model=result.model, tokens=tokens))
            model_issues = ModelReview.model_validate(result.data).issues
        except (LLMError, ValueError) as error:
            model_issues = None
            notes.append(f"The model check could not run ({error}); the options were checked by rules only.")

    # --- attach the reviews ---------------------------------------------------------
    reviewed: dict[str, dict] = {}
    for option in pending:
        ref = f"{option['id']}@{option['version']}"
        mine = None if model_issues is None else [i for i in model_issues if i.option_id == option["id"]]
        reviewed[ref] = apply_review(option, rules[ref], mine)
    options = [reviewed.get(f"{o['id']}@{o['version']}", o) for o in options]
    failed = [o for o in reviewed.values() if not o["review"]["passed"]]
    passed = [o for o in reviewed.values() if o["review"]["passed"]]
    emit(events.activity(f"Options review: {len(passed)} passed, {len(failed)} did not"))

    retries = state.get("option_retries", 0)
    update = {"options": options, "llm_calls": llm_calls, "option_problems": {}}

    if failed and retries < MAX_REVIEW_RETRIES and calls_left(dict(state), context) >= 2:  # a redraft and its review
        return Command(update={**update, "option_feedback": {o["id"]: feedback_for(o) for o in failed}, "options_notes": notes}, goto="draft_options")

    for option in failed:
        why = "; ".join(feedback_for(option)) or "it did not pass review"
        notes.append(f"{option['id']} (version {option['version']}) did not pass review and is not presented: {why}")
    return Command(update={**update, "option_feedback": {}, "options_notes": notes}, goto="select_or_revise")
