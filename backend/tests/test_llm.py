"""
Tests for the language-model clients (app/llm/).

No test here calls the real Groq service. GroqLLM is given a fake transport
that answers from recorded-style data (LEARNING_GUIDE.md topic 33), so we can
check exactly what request it sends and how it handles every kind of reply.
"""

import json

import httpx
import pytest

from app.llm.base import LLMError
from app.llm.factory import build_llm
from app.llm.fixture import FIXTURE_NOTE, FixtureLLM
from app.llm.groq import GROQ_URL, GroqLLM
from app.models.brief_draft import BriefDraft
from tests.conftest import make_settings

ASK = dict(step="intake", system="instructions", user="material", schema_name="brief_draft",
           schema=BriefDraft.model_json_schema())


def groq_with(handler) -> GroqLLM:
    return GroqLLM(api_key="FAKE-KEY-1234567890", model="test-model", transport=httpx.MockTransport(handler),
                   sleep=_no_wait)


async def _no_wait(seconds: float) -> None:
    """Rate-limit waits return at once in tests (the real client really waits)."""
    WAITS.append(seconds)


WAITS: list[float] = []


def reply(content: dict, usage: dict | None = None) -> httpx.Response:
    body = {"model": "test-model", "choices": [{"message": {"content": json.dumps(content)}}]}
    if usage is not None:
        body["usage"] = usage
    return httpx.Response(200, json=body)


async def test_groq_sends_a_strict_structured_output_request():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["authorization"]
        seen["body"] = json.loads(request.content)
        return reply({"ok": True}, usage={"prompt_tokens": 11, "completion_tokens": 7})

    result = await groq_with(handler).complete_json(**ASK)

    assert seen["url"] == GROQ_URL
    assert seen["auth"] == "Bearer FAKE-KEY-1234567890"
    assert seen["body"]["model"] == "test-model"
    assert [m["role"] for m in seen["body"]["messages"]] == ["system", "user"]
    format_ = seen["body"]["response_format"]
    assert format_["type"] == "json_schema"
    assert format_["json_schema"]["strict"] is True
    assert format_["json_schema"]["name"] == "brief_draft"
    assert (result.data, result.input_tokens, result.output_tokens) == ({"ok": True}, 11, 7)


async def test_token_counts_stay_none_when_the_service_does_not_report_them():
    result = await groq_with(lambda request: reply({"ok": True})).complete_json(**ASK)
    assert result.input_tokens is None and result.output_tokens is None


async def test_an_error_reply_becomes_a_clear_error_without_the_key():
    def handler(request):
        return httpx.Response(400, json={"error": {"message": "Bad request body"}})

    with pytest.raises(LLMError) as caught:
        await groq_with(handler).complete_json(**ASK)
    assert "400" in str(caught.value) and "Bad request body" in str(caught.value)
    assert "FAKE-KEY" not in str(caught.value)


async def test_a_rate_limit_is_waited_out_and_then_the_call_succeeds():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(429, json={"error": {"message": "Rate limit reached. Please try again in 2.5s."}})
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"ok": true}'}}], "model": "m"})

    WAITS.clear()
    result = await groq_with(handler).complete_json(**ASK)
    assert result.data == {"ok": True} and calls["n"] == 3
    assert WAITS == [3.0, 3.0]  # the "try again in 2.5s" hint, plus half a second


async def test_a_rate_limit_that_persists_or_asks_too_long_becomes_a_clear_error():
    def forever(request):
        return httpx.Response(429, headers={"retry-after": "1"}, json={"error": {"message": "Rate limit reached"}})

    with pytest.raises(LLMError, match="429"):
        await groq_with(forever).complete_json(**ASK)

    def too_long(request):
        return httpx.Response(429, headers={"retry-after": "900"}, json={"error": {"message": "daily limit"}})

    WAITS.clear()
    with pytest.raises(LLMError, match="429"):
        await groq_with(too_long).complete_json(**ASK)
    assert WAITS == []  # 900 s is over the limit: no wait at all


async def test_chat_sends_tools_and_reads_back_a_tool_call():
    seen = {}

    def handler(request):
        seen.update(json.loads(request.content))
        return httpx.Response(200, json={"model": "m", "usage": {"prompt_tokens": 10, "completion_tokens": 5},
                                         "choices": [{"message": {"content": "", "tool_calls": [
                                             {"id": "call_1", "type": "function",
                                              "function": {"name": "search_github", "arguments": '{"query": "pdf parser"}'}}]}}]})

    tools = [{"type": "function", "function": {"name": "search_github", "description": "d", "parameters": {"type": "object"}}}]
    result = await groq_with(handler).chat(step="agent:x", messages=[{"role": "user", "content": "hi"}], tools=tools)
    assert seen["tools"] == tools and seen["tool_choice"] == "required"
    call = result.tool_calls[0]
    assert (call.id, call.name, call.arguments) == ("call_1", "search_github", {"query": "pdf parser"})
    assert (result.input_tokens, result.output_tokens) == (10, 5)


async def test_tool_arguments_that_are_not_json_are_kept_raw_not_guessed():
    def handler(request):
        return httpx.Response(200, json={"choices": [{"message": {"tool_calls": [
            {"id": "c", "function": {"name": "search_github", "arguments": "not json"}}]}}]})

    result = await groq_with(handler).chat(step="agent:x", messages=[], tools=[])
    assert result.tool_calls[0].arguments is None and result.tool_calls[0].raw_arguments == "not json"


async def test_a_network_failure_becomes_a_clear_error():
    def handler(request):
        raise httpx.ConnectError("no route")

    with pytest.raises(LLMError, match="could not reach"):
        await groq_with(handler).complete_json(**ASK)


async def test_a_reply_that_is_not_json_becomes_a_clear_error():
    def handler(request):
        return httpx.Response(200, json={"choices": [{"message": {"content": "sorry, I cannot"}}]})

    with pytest.raises(LLMError, match="not the expected JSON"):
        await groq_with(handler).complete_json(**ASK)


def test_the_brief_draft_schema_meets_strict_mode_rules():
    """Strict mode needs every field required and no extra fields allowed, in every object."""
    schema = BriefDraft.model_json_schema()
    objects = [schema, *schema.get("$defs", {}).values()]
    for item in objects:
        assert item["additionalProperties"] is False
        assert set(item["required"]) == set(item["properties"])


# --- The fixture model ------------------------------------------------------------
async def test_the_fixture_model_gives_a_valid_draft_and_says_it_is_a_fixture():
    llm = FixtureLLM()
    result = await llm.complete_json(**{**ASK, "user": "A notes app for me. It must work offline. It has tags."})
    draft = BriefDraft.model_validate(result.data)
    assert FIXTURE_NOTE in draft.unknowns
    assert "It must work offline." not in draft.must_have  # a limit is not a feature
    assert draft.deployment is not None
    assert result.model == "fixture" and result.input_tokens is None
    assert llm.calls == ["intake"]


async def test_the_fixture_model_is_repeatable():
    first = await FixtureLLM().complete_json(**{**ASK, "user": "A wiki for my team."})
    second = await FixtureLLM().complete_json(**{**ASK, "user": "A wiki for my team."})
    assert first.data == second.data


# --- Choosing a client ------------------------------------------------------------
def test_fixture_mode_builds_the_fixture_client(tmp_path):
    assert build_llm(make_settings(tmp_path)).mode == "fixture"


def test_live_mode_builds_the_groq_client(tmp_path):
    settings = make_settings(tmp_path, llm_mode="live", llm_provider="groq", llm_model="m", groq_api_key="FAKE-KEY-1234567890")
    client = build_llm(settings)
    assert isinstance(client, GroqLLM) and client.mode == "live"


def test_an_unsupported_provider_is_refused(tmp_path):
    settings = make_settings(tmp_path, llm_mode="live", llm_provider="other", llm_model="m")
    with pytest.raises(ValueError, match="not supported"):
        build_llm(settings)


async def test_a_rejected_tool_call_is_returned_as_a_problem_not_an_error():
    """Seen live: Groq answers 400 when tool arguments do not match the schema."""
    def handler(request):
        return httpx.Response(400, json={"error": {"code": "tool_use_failed", "type": "invalid_request_error",
                                                   "message": "Tool call validation failed: missing properties: 'name'"}})

    result = await groq_with(handler).chat(step="agent:x", messages=[], tools=[])
    assert result.tool_calls == [] and "missing properties" in result.problem


# --- Azure OpenAI ----------------------------------------------------------------------
async def test_azure_sends_the_deployment_url_key_header_and_no_temperature():
    from app.llm.azure import AzureOpenAILLM

    seen = {}

    def answer(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["headers"] = dict(request.headers)
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"model": "gpt-5.1", "choices": [{"message": {"content": "{\"a\": \"b\"}"}}],
                                         "usage": {"prompt_tokens": 1, "completion_tokens": 1}})

    llm = AzureOpenAILLM(api_key="k", endpoint="https://x.openai.azure.com/", deployment="dep", api_version="2025-04-01-preview",
                         transport=httpx.MockTransport(answer))
    await llm.complete_json(step="s", system="s", user="u", schema_name="n", schema={"type": "object"})
    assert seen["url"] == "https://x.openai.azure.com/openai/deployments/dep/chat/completions?api-version=2025-04-01-preview"
    assert seen["headers"]["api-key"] == "k" and "authorization" not in seen["headers"]
    assert "model" not in seen["body"] and "temperature" not in seen["body"]
    assert seen["body"]["response_format"]["json_schema"]["strict"] is False


async def test_a_timeout_is_retried_before_the_call_fails():
    from app.llm.groq import GroqLLM

    attempts = {"n": 0}

    def answer(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise httpx.ReadTimeout("slow", request=request)
        return httpx.Response(200, json={"model": "m", "choices": [{"message": {"content": "{\"a\": 1}"}}], "usage": {}})

    async def no_wait(seconds):
        return None

    llm = GroqLLM(api_key="k", model="m", transport=httpx.MockTransport(answer), sleep=no_wait)
    result = await llm.complete_json(step="s", system="s", user="u", schema_name="n", schema={"type": "object"})
    assert result.data == {"a": 1} and attempts["n"] == 3


async def test_a_paid_provider_sends_several_requests_at_once_and_groq_one():
    import asyncio as aio

    from app.llm.groq import GroqLLM

    async def peak_for(max_concurrency):
        in_flight = {"now": 0, "peak": 0}

        async def handler(request):
            in_flight["now"] += 1
            in_flight["peak"] = max(in_flight["peak"], in_flight["now"])
            await aio.sleep(0.02)
            in_flight["now"] -= 1
            return httpx.Response(200, json={"model": "m", "choices": [{"message": {"content": "{}"}}], "usage": {}})

        llm = GroqLLM(api_key="k", model="m", transport=httpx.MockTransport(handler), max_concurrency=max_concurrency)
        await aio.gather(*[llm.complete_json(step="s", system="s", user="u", schema_name="n", schema={}) for _ in range(6)])
        return in_flight["peak"]

    assert await peak_for(1) == 1
    assert await peak_for(4) == 4
