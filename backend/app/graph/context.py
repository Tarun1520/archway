"""
The run context: read-only things a node needs but must not change.

What this file does
    Bundles the language-model client and the call cap for one run. It is
    passed in when the run starts:  graph.astream(..., context=RunContext(...))
    and each node receives it as `runtime.context`.

Why the model client lives here and not in the state
    The state is saved to disk after every step; a network client cannot be
    saved. Context is not saved. It is also what makes nodes "plug and play":
    a test passes a fixture client here and the node code does not change.

Learn more: LEARNING_GUIDE.md topic 19.
"""

from dataclasses import dataclass, field

from app.decisions.client import DecisionClient
from app.integrations.factory import Integrations
from app.llm.base import LLMClient
from app.policy.eligibility import EligibilityPolicy
from app.tools.base import RunBudget


@dataclass(frozen=True)
class RunContext:
    llm: LLMClient
    max_llm_calls: int  # the per-run cap; reaching it stops further model calls

    # --- The research team (Phase 3) ---------------------------------------------
    # The outside world the agents' tools read (GitHub, PyPI, npm, web pages).
    integrations: Integrations | None = None
    # The run's shared counters. Built by the service from the usage already
    # recorded for this run, so a resumed run continues the same budget.
    budget: RunBudget | None = field(default=None, compare=False)
    # Phase 4
    decisions: DecisionClient | None = None
    max_jev_calls: int = 40
    eligibility_policy: EligibilityPolicy | None = None
