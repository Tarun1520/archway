"""
Node: check_prompts. Phase 6: the prompt quality rubric, and the one retry.

    every check passes                 -> export, outcome "full"
    something fails, retry left        -> build_roadmap again, shown exactly what failed
    something still fails after it     -> export anyway, outcome "partial", every failure listed in the notes

LEARNING NOTE: a bounded loop with an honest exit
    The roadmap gets ONE more attempt (MAX_RETRIES). After that the plan is exported as it is, labelled PARTIAL,
    with every failed line visible, instead of looping until the budget runs out or pretending it passed.
    (The same shape as the options review gate, LEARNING_GUIDE.md topic 65.)
"""

from typing import Literal

from langgraph.runtime import Runtime
from langgraph.types import Command

from app.graph import events
from app.graph.context import RunContext
from app.graph.state import WorkflowState
from app.models.plan import PromptFile, Roadmap
from app.promptgen.rubric import check_pack

NODE = "check_prompts"
MAX_RETRIES = 1


async def check_prompts(state: WorkflowState, runtime: Runtime[RunContext]) -> Command[Literal["build_roadmap", "export"]]:
    emit = runtime.stream_writer
    emit(events.node_started(NODE))
    roadmap = Roadmap.model_validate(state["roadmap"])
    files = [PromptFile.model_validate(f) for f in state.get("plan_files", [])]
    checked, rubric_failures = check_pack(files, roadmap, dict(state))
    failures = list(state.get("plan_issues") or []) + rubric_failures
    update = {"plan_files": [f.model_dump(mode="json") for f in checked]}

    if failures and state.get("plan_retries", 0) < MAX_RETRIES:
        emit(events.activity(f"Plan: {len(failures)} check(s) failed; the roadmap gets one more attempt"))
        return Command(update={**update, "plan_issues": failures, "plan_retries": state.get("plan_retries", 0) + 1}, goto="build_roadmap")

    if failures:
        emit(events.activity(f"Plan: {len(failures)} check(s) still fail after the retry; the plan is exported as partial"))
        notes = [f"Not passed: {failure}" for failure in failures]
    else:
        emit(events.activity("Plan: every prompt passed every rubric check"))
        notes = []
    return Command(
        update={**update, "plan_passed": not failures, "plan_outcome": "partial" if failures else "full", "plan_notes": [*state.get("plan_notes", []), *notes]},
        goto="export",
    )
