"""
AzureOpenAILLM: the language-model client for an Azure OpenAI deployment.

Why it is a few lines
    Azure OpenAI speaks the same chat-completions format as Groq (messages,
    tools, tool_calls, usage), so this class reuses everything in GroqLLM:
    the rate-limit waiting, one request at a time, tool-call parsing, and
    safe error text. Only the differences are written here.

What differs (LEARNING_GUIDE.md topic 58)
    - URL: {endpoint}/openai/deployments/{deployment}/chat/completions
           ?api-version=...     The deployment name replaces the model name.
    - Header: `api-key: <key>` instead of `Authorization: Bearer <key>`.
    - No `model` field in the body (the deployment already decides it).
    - No `temperature`: the gpt-5 family are reasoning models and refuse any
      value but the default.
    - `strict` structured output is turned off: Azure's strict mode demands
      every field be required, which our Pydantic schemas (with defaults)
      are not. The reply is still checked by Pydantic after it arrives.
    - `parallel_tool_calls` is on: a reply may ask for several tools at once,
      and the agent loop runs them all (one model call instead of several).

How it plugs in
    app/llm/factory.py returns this when LLM_PROVIDER=azure.
"""

from typing import Any

from app.llm.groq import GroqLLM


class AzureOpenAILLM(GroqLLM):
    def __init__(self, *, api_key: str, endpoint: str, deployment: str, api_version: str, **kwargs: Any):
        super().__init__(api_key=api_key, model=deployment, **kwargs)
        self._endpoint = endpoint.rstrip("/")
        self._api_version = api_version

    def _target(self) -> tuple[str, dict[str, str]]:
        url = f"{self._endpoint}/openai/deployments/{self._model}/chat/completions?api-version={self._api_version}"
        return url, {"api-key": self._api_key}

    def _shape(self, body: dict[str, Any]) -> dict[str, Any]:
        shaped = {k: v for k, v in body.items() if k not in ("model", "temperature")}
        if "tools" in shaped:
            shaped["parallel_tool_calls"] = True
        schema = (shaped.get("response_format") or {}).get("json_schema")
        if schema:
            shaped["response_format"] = {"type": "json_schema", "json_schema": {**schema, "strict": False}}
        return shaped
