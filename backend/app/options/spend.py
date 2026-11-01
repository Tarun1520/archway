"""
Spending the run's model-call allowance (IMPLEMENTATION_GUIDE.md 5.3: no unlimited default).

The research agents spend from the run's shared budget (app/tools/base.py `RunBudget`, built from the usage
already saved for the run), so the options nodes spend from the SAME budget: one cap for the whole run, and a
resumed run cannot start over. Where a run has no budget (a unit test building a context by hand), the older
per-run counter in the workflow state is used instead.
"""

from typing import Any

from app.graph.context import RunContext


def take_model_call(state: dict[str, Any], context: RunContext) -> bool:
    """Spend one model call if the allowance has one left. False means: do not call."""
    if context.budget is not None:
        return context.budget.take("llm")
    return state.get("llm_calls", 0) < context.max_llm_calls


def calls_left(state: dict[str, Any], context: RunContext) -> int:
    if context.budget is not None:
        return context.budget.left("llm")
    return context.max_llm_calls - state.get("llm_calls", 0)
