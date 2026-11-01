"""
FastFirstLLM: try a quick model first, and fall back to the steady one.

What this file does
    Archy talks to a person, so every second of waiting is heard. His tiny
    questions ("is this an idea or small talk?") are answered much faster by a
    small, quick model than by the project's main model. This wrapper sends
    each `complete_json` call to the quick model first and, if that model is
    slow, rate-limited or fails, asks the main model instead. The caller cannot
    tell the difference.

LEARNING NOTE: a wrapper that has the same shape as what it wraps
    FastFirstLLM has `complete_json` like every LLMClient, so it plugs in
    wherever one is expected. This is the "decorator" idea: add behaviour
    around something without changing it.

Only `complete_json` is offered: the voice endpoints use nothing else.
"""

import asyncio
from typing import Any

from app.llm.base import LLMClient, LLMError, LLMResult

QUICK_LIMIT_SECONDS = 6.0  # past this, the quick model is not quick: ask the steady one


class FastFirstLLM:
    def __init__(self, quick: LLMClient, steady: LLMClient, limit_seconds: float = QUICK_LIMIT_SECONDS):
        self._quick = quick
        self._steady = steady
        self._limit = limit_seconds
        self.mode = steady.mode

    async def complete_json(self, *, step: str, system: str, user: str, schema_name: str, schema: dict[str, Any]) -> LLMResult:
        try:
            return await asyncio.wait_for(
                self._quick.complete_json(step=step, system=system, user=user, schema_name=schema_name, schema=schema),
                timeout=self._limit,
            )
        except (LLMError, TimeoutError):
            return await self._steady.complete_json(step=step, system=system, user=user, schema_name=schema_name, schema=schema)
