"""
The interface every language-model client follows.

What this file does
    Two methods:
      complete_json   "here are instructions and material; answer in this JSON
                      shape". One reply, no tools. (The brief steps.)
      chat            a conversation in which the model may ask for TOOLS.
                      This is what makes an agent (app/agents/runtime.py).

LEARNING NOTE: what is a Protocol?
    A Protocol describes a shape: "anything that has these methods counts".
    FixtureLLM and GroqLLM do not inherit from LLMClient; they simply have a
    matching `complete_json`, and that is enough. Code that receives an
    LLMClient cannot tell which one it got. That is "plug and play".

How it plugs in
    Graph nodes receive an LLMClient through the run context
    (app/graph/context.py) and call `complete_json` on it.
"""

from dataclasses import dataclass
from typing import Any, Protocol

from app.models.common import ServiceMode


@dataclass(frozen=True)
class LLMResult:
    """What came back from one model call."""

    data: dict[str, Any]  # the parsed JSON object
    model: str | None  # the model that answered, as reported by the service
    # Token counts are kept only when the service reported them. None is
    # "not reported", never zero.
    input_tokens: int | None
    output_tokens: int | None


class LLMError(Exception):
    """A model call failed. The message is safe to show: it never contains a key."""


@dataclass(frozen=True)
class ToolCall:
    """The model asking for one tool to be run. It is only a REQUEST."""

    id: str
    name: str
    # The parsed arguments, or None when the model sent text that is not a
    # JSON object. The agent loop then tells the model its call was invalid.
    arguments: dict[str, Any] | None
    raw_arguments: str


@dataclass(frozen=True)
class ChatResult:
    """One reply in a conversation with tools."""

    content: str | None  # any text the model wrote
    tool_calls: list[ToolCall]
    model: str | None
    input_tokens: int | None
    output_tokens: int | None
    # Set when the service REJECTED the model's tool call (for example, its
    # arguments did not match the tool's schema). The agent is told why and
    # may try again; the run does not fail for it.
    problem: str | None = None


class LLMClient(Protocol):
    mode: ServiceMode  # "live" or "fixture": recorded with every call

    async def complete_json(
        self,
        *,
        step: str,  # which workflow step is asking, e.g. "intake"
        system: str,  # the instructions
        user: str,  # the material to work on
        schema_name: str,
        schema: dict[str, Any],  # the JSON Schema the answer must match
    ) -> LLMResult: ...

    async def chat(
        self,
        *,
        step: str,  # who is asking, e.g. "agent:component_scout"
        messages: list[dict[str, Any]],  # the conversation, in the OpenAI chat format
        tools: list[dict[str, Any]],  # the tools this agent may ask for
    ) -> ChatResult: ...
