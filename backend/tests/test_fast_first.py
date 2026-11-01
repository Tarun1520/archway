"""FastFirstLLM: the quick model answers when it can; the steady one steps in when it cannot."""

import asyncio

import pytest

from app.llm.base import LLMError, LLMResult
from app.llm.fast_first import FastFirstLLM

ASK = dict(step="s", system="x", user="y", schema_name="n", schema={})


class Model:
    mode = "live"

    def __init__(self, name: str, *, fail: bool = False, slow: bool = False):
        self.name, self.fail, self.slow, self.calls = name, fail, slow, 0

    async def complete_json(self, **_):
        self.calls += 1
        if self.slow:
            await asyncio.sleep(1)
        if self.fail:
            raise LLMError("rate limited")
        return LLMResult(data={"from": self.name}, model=self.name, input_tokens=None, output_tokens=None)


@pytest.mark.asyncio
async def test_the_quick_model_answers_when_it_can():
    quick, steady = Model("quick"), Model("steady")
    result = await FastFirstLLM(quick, steady).complete_json(**ASK)
    assert result.data == {"from": "quick"} and steady.calls == 0


@pytest.mark.asyncio
async def test_a_failing_quick_model_falls_back_to_the_steady_one():
    result = await FastFirstLLM(Model("quick", fail=True), Model("steady")).complete_json(**ASK)
    assert result.data == {"from": "steady"}


@pytest.mark.asyncio
async def test_a_slow_quick_model_falls_back_to_the_steady_one():
    result = await FastFirstLLM(Model("quick", slow=True), Model("steady"), limit_seconds=0.05).complete_json(**ASK)
    assert result.data == {"from": "steady"}
