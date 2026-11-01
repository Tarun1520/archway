"""
Node: intake. Reads what the user said and drafts a brief.

What this node does, in order
    0. If the person has only said hello (no project described), it stops
       here WITHOUT calling the model and asks "what would you like to
       build?". Nothing is drafted, so there is nothing to confirm yet.
    1. Checks the call cap. If the run has used its model calls, it stops
       calling and says so (IMPLEMENTATION_GUIDE.md section 5.3).
    2. Asks the language model for a BriefDraft (structured output).
    3. Checks the reply against the BriefDraft contract.
    4. If the model says no project was described, asks the idea question
       (the same reply as step 0) instead of building a brief about nothing.
    5. Hands the draft to plain Python (app/briefing/builder.py), which makes
       the real ProjectBrief: ids, version, stated constraints, conflicts.
    6. Asks the clarification policy whether any question is worth asking.

Who decides what
    The MODEL only proposes a draft. Everything that must be reliable
    (keeping constraints, flagging conflicts, limiting questions, the cap,
    "is there a project at all") is decided by code. This is "models judge,
    code decides".

What it returns
    Only the state keys it changes: brief, open_questions, llm_calls.

Learn more: LEARNING_GUIDE.md topics 7, 19 and 23.
"""

from pydantic import ValidationError

from langgraph.runtime import Runtime

from app.briefing.builder import build_brief
from app.graph import events
from app.graph.context import RunContext
from app.graph.prompts import INTAKE_SYSTEM_PROMPT, intake_user_prompt
from app.graph.state import WorkflowState
from app.llm.base import LLMError
from app.models.brief import ProjectBrief
from app.models.brief_draft import BriefDraft
from app.policy.clarification import IDEA_QUESTION, has_project, questions_for
from app.policy.small_talk import only_small_talk

NODE = "intake"

# The user is asked architecture questions at most this many times per run.
# After that the workflow moves on with what it has (unknowns stay listed as
# unknown). Asking "what would you like to build?" does not count: it is not
# an architecture question, and it may be needed more than once.
MAX_CLARIFY_ROUNDS = 1


def _ask_for_the_idea(emit, why: str, llm_calls: int | None = None) -> dict:
    """The reply when there is nothing to draft yet."""
    emit(events.activity(why))
    update: dict = {"open_questions": [IDEA_QUESTION.model_dump()]}
    if llm_calls is not None:
        update["llm_calls"] = llm_calls
    return update


async def intake(state: WorkflowState, runtime: Runtime[RunContext]) -> dict:
    # `emit` sends a progress event straight away, before this node finishes.
    emit = runtime.stream_writer
    emit(events.node_started(NODE))

    context = runtime.context
    previous = ProjectBrief.model_validate(state["brief"]) if state["brief"] else None

    # --- 0. Only a greeting so far? No model call needed -----------------------
    if previous is None and only_small_talk(state["user_texts"]):
        return _ask_for_the_idea(emit, "Intake: no project described yet, asking what you would like to build")

    # --- 1. The call cap -----------------------------------------------------
    if state["llm_calls"] >= context.max_llm_calls:
        if previous is None:
            raise LLMError(f"the cap of {context.max_llm_calls} model calls was reached before a brief could be drafted")
        emit(events.activity(
            f"Model call cap reached ({context.max_llm_calls}). Keeping brief version {previous.version} "
            "without re-reading your answers."
        ))
        return {"open_questions": []}  # go on to confirmation with what we have

    # --- 2. Ask the model ----------------------------------------------------
    emit(events.activity("Intake: reading your idea"))
    result = await context.llm.complete_json(
        step=NODE,
        system=INTAKE_SYSTEM_PROMPT,
        user=intake_user_prompt(state["user_texts"], state.get("asked_questions", [])),
        schema_name="brief_draft",
        schema=BriefDraft.model_json_schema(),
    )
    # Count the call as soon as it has happened, whatever it returned.
    tokens = None
    if result.input_tokens is not None and result.output_tokens is not None:
        tokens = result.input_tokens + result.output_tokens
    emit(events.usage(service="llm", mode=context.llm.mode, model=result.model, tokens=tokens))
    llm_calls = state["llm_calls"] + 1

    # --- 3. Check the reply --------------------------------------------------
    try:
        draft = BriefDraft.model_validate(result.data)
    except ValidationError as error:
        raise LLMError(f"the model's reply did not match the brief shape ({error.error_count()} problems)") from error

    # --- 4. No project described? Ask, do not invent one ----------------------
    if previous is None and not has_project(draft):
        return _ask_for_the_idea(
            emit, "Intake: your message did not describe a project yet, asking what you would like to build", llm_calls
        )

    # --- 5. Build the real brief with plain Python ---------------------------
    brief = build_brief(
        run_id=state["run_id"],
        draft=draft,
        previous=previous,
        user_texts=state["user_texts"],
        assumed_topics=state["assumed_topics"],
    )
    emit(events.activity(f"Intake: brief version {brief.version} drafted"))
    if brief.constraints.stated:
        emit(events.activity(f"Kept {len(brief.constraints.stated)} stated constraint(s) word for word"))
    for conflict in brief.conflicts:
        emit(events.activity(f"Conflict flagged: {conflict.description}"))

    # --- 6. Is any question worth asking? ------------------------------------
    questions = []
    if state["clarify_rounds"] < MAX_CLARIFY_ROUNDS:
        questions = questions_for(draft, state["asked_topics"])

    return {
        "brief": brief.model_dump(mode="json"),
        "open_questions": [question.model_dump() for question in questions],
        "llm_calls": llm_calls,
    }
