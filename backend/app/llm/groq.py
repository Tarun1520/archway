"""
GroqLLM: the real language-model client, talking to Groq's API.

What this file does
    Sends HTTP requests to Groq's chat-completions endpoint, in two ways:
      complete_json   asks for "structured output": JSON matching a schema
      chat            offers TOOLS: the model may answer with tool calls

Verified against Groq's documentation (console.groq.com/docs)
    - Endpoint: POST https://api.groq.com/openai/v1/chat/completions
    - Structured output: response_format = {"type": "json_schema", "json_schema":
      {"name": ..., "strict": true, "schema": {...}}}
    - Tools: "tools": [{"type": "function", "function": {name, description,
      parameters}}]. The reply's message has "tool_calls", each with id and
      function.name / function.arguments (a JSON STRING). Results go back as
      {"role": "tool", "tool_call_id": ..., "content": ...}.
      The gpt-oss models do not call tools in parallel: one call per reply.
    - Rate limits: HTTP 429, with a `retry-after` header in seconds.
      Checked live on this account: 8,000 tokens per minute, 1,000 requests
      per day for openai/gpt-oss-120b.

Waiting out a rate limit
    A team of agents makes many calls, so a 429 is normal, not a failure.
    This client waits (up to MAX_WAIT_SECONDS each time, at most
    MAX_RATE_LIMIT_RETRIES times) and tries again. Longer waits, or too many,
    become an LLMError the run reports. Requests are also sent one at a time
    (max_concurrency=1), because parallel agents would only race into the limit.

LEARNING NOTE: the anatomy of a chat request
    "messages" is the conversation so far. The model has no memory:
    everything it should know must be in this one request, every time.

How it plugs in
    app/llm/factory.py returns this when LLM_MODE=live and LLM_PROVIDER=groq.
"""

import asyncio
import json
import re
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from app.security.scrub import scrub
from app.llm.base import ChatResult, LLMError, LLMResult, ToolCall

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
TIMEOUT_SECONDS = 120.0  # never wait forever for a model (reasoning models can think for a minute)
MAX_TRANSIENT_RETRIES = 2  # a timeout or a dropped connection is tried again this many times
MAX_WAIT_SECONDS = 60.0  # the longest single wait for a rate limit
MAX_RATE_LIMIT_RETRIES = 4

Sleep = Callable[[float], Awaitable[None]]


class ToolCallRejected(LLMError):
    """Groq checked the model's tool call against the tool's schema, and it did not match."""


def _is_tool_call_rejection(response: httpx.Response) -> bool:
    try:
        error = response.json().get("error") or {}
    except ValueError:
        return False
    return error.get("code") == "tool_use_failed" or str(error.get("message", "")).startswith("Tool call validation failed")


def _wait_seconds(response: httpx.Response) -> float:
    """How long Groq asked us to wait: the header, or the "try again in 5.2s" text."""
    header = response.headers.get("retry-after")
    if header:
        try:
            return float(header)
        except ValueError:
            pass
    match = re.search(r"try again in ([0-9.]+)s", response.text)
    return float(match.group(1)) if match else MAX_WAIT_SECONDS


class GroqLLM:
    mode = "live"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        transport: httpx.AsyncBaseTransport | None = None,
        sleep: Sleep = asyncio.sleep,
        max_concurrency: int = 1,
    ):
        self._api_key = api_key
        self._model = model
        # `transport` exists so tests can answer requests from recorded data
        # instead of the internet (LEARNING_GUIDE.md topic 33).
        self._transport = transport
        self._sleep = sleep
        # LEARNING NOTE: a semaphore is a lock that lets N callers in at once
        #   Groq's free tier allows 8,000 tokens a minute, so parallel agents
        #   only race into its rate limit: it keeps ONE request at a time.
        #   A paid provider (Azure) can take several, so parallel scouts really
        #   run in parallel. Found live: with one-at-a-time, five "parallel"
        #   scouts took turns, and a run took about nine minutes.
        self._gate = asyncio.Semaphore(max(1, max_concurrency))

    # --- Hooks: a provider with the same chat shape overrides only these ----
    def _target(self) -> tuple[str, dict[str, str]]:
        """Where to send a request, and the headers (the key travels in a header)."""
        return GROQ_URL, {"Authorization": f"Bearer {self._api_key}"}

    def _shape(self, body: dict[str, Any]) -> dict[str, Any]:
        """Adjust a request body for the provider. Groq needs no change."""
        return body

    async def _post(self, body: dict[str, Any]) -> dict[str, Any]:
        """Send one request, waiting out rate limits. Returns the parsed reply."""
        url, headers = self._target()
        body = self._shape(body)
        async with self._gate:
            transient = 0
            for attempt in range(MAX_RATE_LIMIT_RETRIES + MAX_TRANSIENT_RETRIES + 1):
                try:
                    async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS, transport=self._transport) as client:
                        # The key is in the headers only. It is never logged and
                        # never put into an error message.
                        response = await client.post(url, json=body, headers=headers)
                except httpx.HTTPError as error:
                    # LEARNING NOTE: one slow call must not end a whole run
                    #   Found live: a single 60 s timeout stopped a ten-minute
                    #   research run. Timeouts and dropped connections are
                    #   usually momentary, so they are tried again first.
                    transient += 1
                    if transient > MAX_TRANSIENT_RETRIES:
                        if isinstance(error, httpx.TimeoutException):
                            raise LLMError(f"the model did not answer within {int(TIMEOUT_SECONDS)} seconds") from error
                        raise LLMError(f"could not reach the model service ({type(error).__name__})") from error
                    await self._sleep(2.0 * transient)
                    continue
                if response.status_code >= 500 and transient < MAX_TRANSIENT_RETRIES:
                    transient += 1
                    await self._sleep(2.0 * transient)
                    continue

                if response.status_code == 429:
                    wait = _wait_seconds(response)
                    if wait > MAX_WAIT_SECONDS or attempt >= MAX_RATE_LIMIT_RETRIES + transient:
                        raise LLMError(f"the model service answered HTTP 429: {_error_text(response)}")
                    await self._sleep(wait + 0.5)
                    continue
                if response.status_code == 400 and _is_tool_call_rejection(response):
                    raise ToolCallRejected(_error_text(response))
                if response.status_code != 200:
                    raise LLMError(f"the model service answered HTTP {response.status_code}: {_error_text(response)}")
                try:
                    return response.json()
                except ValueError as error:
                    raise LLMError("the model service returned a reply that was not the expected JSON") from error
        raise LLMError("the model service kept answering HTTP 429")  # not reached

    async def complete_json(self, *, step: str, system: str, user: str, schema_name: str, schema: dict[str, Any]) -> LLMResult:
        payload = await self._post({
            "model": self._model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "response_format": {"type": "json_schema", "json_schema": {"name": schema_name, "strict": True, "schema": schema}},
            # 0 = pick the most likely answer each time, for steadier results.
            "temperature": 0,
        })
        try:
            content = payload["choices"][0]["message"]["content"]
            data = json.loads(content)
        except (KeyError, IndexError, TypeError, ValueError) as error:
            raise LLMError("the model service returned a reply that was not the expected JSON") from error
        if not isinstance(data, dict):
            raise LLMError("the model returned JSON that is not an object")
        usage = payload.get("usage") or {}
        return LLMResult(data=data, model=payload.get("model"),
                         input_tokens=usage.get("prompt_tokens"), output_tokens=usage.get("completion_tokens"))

    async def chat(self, *, step: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> ChatResult:
        try:
            payload = await self._post({
                "model": self._model,
                "messages": messages,
                "tools": tools,
                # "required": the model must answer with a tool call. Every agent
                # ends by calling a "submit" tool, so free text is never the answer.
                "tool_choice": "required",
                "temperature": 0,
            })
        except ToolCallRejected as rejected:
            # Seen in a live run: the model sent capabilities without a "name".
            # Groq refuses such a call with HTTP 400. That is the model's
            # mistake to correct, not a reason to stop the whole run.
            return ChatResult(content=None, tool_calls=[], model=self._model, input_tokens=None,
                              output_tokens=None, problem=str(rejected))
        try:
            message = payload["choices"][0]["message"]
        except (KeyError, IndexError, TypeError) as error:
            raise LLMError("the model service returned a reply that was not the expected JSON") from error

        calls = []
        for item in message.get("tool_calls") or []:
            function = item.get("function") or {}
            raw = function.get("arguments") or "{}"
            try:
                arguments = json.loads(raw)
                if not isinstance(arguments, dict):
                    arguments = None
            except ValueError:
                arguments = None
            calls.append(ToolCall(id=str(item.get("id", "")), name=str(function.get("name", "")),
                                  arguments=arguments, raw_arguments=raw))
        usage = payload.get("usage") or {}
        return ChatResult(content=message.get("content"), tool_calls=calls, model=payload.get("model"),
                          input_tokens=usage.get("prompt_tokens"), output_tokens=usage.get("completion_tokens"))


def _error_text(response: httpx.Response) -> str:
    """A short, safe description of an error reply from the service."""
    try:
        message = response.json()["error"]["message"]
    except (KeyError, TypeError, ValueError):
        message = response.text
    return scrub(str(message)[:300])  # a service's error text can echo part of the key
