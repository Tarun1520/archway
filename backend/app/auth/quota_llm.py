"""
A model client that stops when an account's monthly token quota runs out.

What this file does
    QuotaLLM(llm, tokens_left) behaves exactly like the model client it wraps, but it counts the tokens each answer
    reports, and refuses the next call once the allowance is used up. The refusal is an LLMError with a plain
    message, which the workflow already handles honestly: the run stops, says why, and can carry on later (next
    month, or after the admin raises the quota) from its last saved step.

LEARNING NOTE: wrapping instead of changing
    Every node and agent already calls `context.llm`. Handing them this wrapper instead (app/workflow/service.py)
    adds the limit everywhere at once, without changing a single node. The same trick as the call cap (topic 19).

Its honest limit
    A call that has started is allowed to finish, so a run can go a little over the quota (by one answer at most).
"""

from typing import Any

from app.llm.base import LLMError

QUOTA_MESSAGE = (
    "Your monthly model-token quota is used up, so the run has stopped at its last saved step. "
    "Ask the admin to raise your quota, or carry on next month."
)


class QuotaLLM:
    def __init__(self, llm: Any, tokens_left: int):
        self._llm = llm
        self.left = tokens_left

    def __getattr__(self, name: str) -> Any:
        # Anything this wrapper does not define (mode, model name ...) comes from the real client.
        return getattr(self._llm, name)

    def _check(self) -> None:
        if self.left <= 0:
            raise LLMError(QUOTA_MESSAGE)

    def _spend(self, result: Any) -> Any:
        used = (getattr(result, "input_tokens", None) or 0) + (getattr(result, "output_tokens", None) or 0)
        self.left -= used
        return result

    async def complete_json(self, **arguments: Any) -> Any:
        self._check()
        return self._spend(await self._llm.complete_json(**arguments))

    async def chat(self, **arguments: Any) -> Any:
        self._check()
        return self._spend(await self._llm.chat(**arguments))
