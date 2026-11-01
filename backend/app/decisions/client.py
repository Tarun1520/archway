"""
The decision client: asks typed questions about a piece of state.

Two implementations, one shape (plug and play, like app/llm/)
    GatewayDecisionClient   live: POST https://ai-gateway.vercel.sh/v1/evaluate
                            (Vercel AI Gateway's decision API; model e.g. typesafe-ai/jev)
    FixtureDecisionClient   offline: fixed, clearly labelled answers, no network

The request (from Vercel's "Decision" docs)
    {"model": "...", "state": <string | object>, "questions": {
        "<name>": {"type": "boolean" | "choice" | "score", "instructions": "...", "criteria": ...}}}
    criteria: boolean -> optional {"true": ..., "false": ...}; choice -> {option: description};
    score -> [labels from lowest to highest].
The answer
    {"model": "...", "answers": {"<name>": {"type": "boolean", "probability": 0.98}
                                 | {"type": "choice", "choice": "...", "probabilities": {...}}
                                 | {"type": "score", "score": 2.97, "probabilities": {"0": ..., "3": ...}}},
     "usage": {"inputTokens": ..., "outputTokens": ...}}

Unavailable is not an error to hide
    If the service cannot answer (no card on the account, network, outage),
    DecisionUnavailable is raised. The caller then records every question as
    "not evaluated" and shows a notice. It never substitutes a chat model's
    opinion under the Jev label (IMPLEMENTATION_GUIDE.md 6.4).
"""

from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx

from app.security.scrub import scrub

GATEWAY_EVALUATE_URL = "https://ai-gateway.vercel.sh/v1/evaluate"
TIMEOUT_SECONDS = 30.0


class DecisionUnavailable(Exception):
    """The decision service could not answer. Its message is safe to show (never contains a key)."""


@dataclass(frozen=True)
class DecisionResponse:
    model: str | None
    answers: dict[str, dict[str, Any]]
    input_tokens: int | None = None
    output_tokens: int | None = None
    raw: dict[str, Any] = field(default_factory=dict)


class DecisionClient(Protocol):
    mode: str

    async def decide(self, *, state: Any, questions: dict[str, dict[str, Any]]) -> DecisionResponse: ...


class GatewayDecisionClient:
    mode = "live"

    def __init__(self, *, api_key: str, model: str, transport: httpx.AsyncBaseTransport | None = None):
        self._api_key = api_key
        self.model = model
        self._transport = transport

    async def decide(self, *, state: Any, questions: dict[str, dict[str, Any]]) -> DecisionResponse:
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS, transport=self._transport) as client:
                response = await client.post(
                    GATEWAY_EVALUATE_URL,
                    json={"model": self.model, "state": state, "questions": questions},
                    # The key is only in this header: never logged, never in an error message.
                    headers={"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"},
                )
        except httpx.HTTPError as error:
            raise DecisionUnavailable(f"the decision service could not be reached ({type(error).__name__})") from error
        if response.status_code != 200:
            try:
                message = str(response.json()["error"]["message"])[:200]
            except (KeyError, TypeError, ValueError):
                message = response.text[:200]
            raise DecisionUnavailable(f"the decision service answered HTTP {response.status_code}: {scrub(message)}")
        try:
            body = response.json()
            answers = body["answers"]
        except (KeyError, TypeError, ValueError) as error:
            raise DecisionUnavailable("the decision service returned a reply that was not the expected JSON") from error
        usage = body.get("usage") or {}
        return DecisionResponse(model=body.get("model"), answers=answers if isinstance(answers, dict) else {},
                                input_tokens=usage.get("inputTokens"), output_tokens=usage.get("outputTokens"), raw=body)


class SystemOneDecisionClient:
    """A server speaking Jev's own wire protocol, POST {base}/v1/systemone: a local Laya today.

    LEARNING NOTE: one protocol, several engines
      Laya (open source, runs on this Mac) serves the same /v1/systemone
      contract as TypeSafe's Jev, so the same client works for either; only
      the base address and key change. The protocol calls a yes/no question
      `noul` and answers it with {"noul": probability}; this client converts
      to and from Archway's `boolean` shape so nothing else needs to know.
    """

    mode = "live"

    def __init__(self, *, base_url: str, model: str | None = None, api_key: str | None = None,
                 transport: httpx.AsyncBaseTransport | None = None, label: str = "laya"):
        self._url = base_url.rstrip("/") + "/v1/systemone"
        self.model = model
        self._api_key = api_key
        self._transport = transport
        self.label = label

    async def decide(self, *, state: Any, questions: dict[str, dict[str, Any]]) -> DecisionResponse:
        wire = {name: ({**q, "type": "noul"} if q["type"] == "boolean" else q) for name, q in questions.items()}
        body: dict[str, Any] = {"state": state if isinstance(state, str) else _as_text(state), "questions": wire}
        if self.model:
            body["model"] = self.model
        headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS, transport=self._transport) as client:
                response = await client.post(self._url, json=body, headers=headers)
        except httpx.HTTPError as error:
            raise DecisionUnavailable(
                f"the {self.label} decision service at {self._url} could not be reached ({type(error).__name__}); "
                "is it running? See backend/services/laya/README.md") from error
        if response.status_code != 200:
            raise DecisionUnavailable(f"the {self.label} decision service answered HTTP {response.status_code}: {scrub(response.text[:200])}")
        try:
            data = response.json()
            answers = {}
            for name, answer in data["answers"].items():
                if answer.get("type") == "noul":
                    answers[name] = {"type": "boolean", "probability": float(answer["noul"])}
                else:
                    answers[name] = answer
        except (KeyError, TypeError, ValueError) as error:
            raise DecisionUnavailable(f"the {self.label} decision service returned an unexpected reply") from error
        usage = data.get("usage") or {}
        model = data.get("model") or self.model
        return DecisionResponse(model=f"{self.label}/{model}" if model and not str(model).startswith(self.label) else model,
                                answers=answers, input_tokens=usage.get("input_tokens"), output_tokens=usage.get("output_tokens"), raw=data)


def _as_text(state: Any) -> str:
    """A compact text rendering of a state object: short models read prose better than nested JSON."""
    if not isinstance(state, dict):
        return str(state)
    lines = []
    for key, value in state.items():
        if isinstance(value, dict):
            inner = "; ".join(f"{k}: {v}" for k, v in value.items() if v not in (None, "", []))
            lines.append(f"{key}: {inner}")
        elif isinstance(value, list):
            lines.extend(f"{key}: {item}" for item in value if item)
        elif value not in (None, ""):
            lines.append(f"{key}: {value}")
    return "\n".join(lines)


class FixtureDecisionClient:
    """Fixed answers for tests and demos. Every receipt it produces is marked jev_mode="fixture"."""

    mode = "fixture"
    model = "fixture-decisions"

    async def decide(self, *, state: Any, questions: dict[str, dict[str, Any]]) -> DecisionResponse:
        answers: dict[str, dict[str, Any]] = {}
        for name, question in questions.items():
            if question["type"] == "boolean":
                # "meets the requirement" yes, "needs review" no: a fixture run reads as a plausible, labelled demo.
                answers[name] = {"type": "boolean", "probability": 0.8 if name.startswith("fit__") else 0.2}
            elif question["type"] == "choice":
                options = list(question["criteria"])
                answers[name] = {"type": "choice", "choice": options[0],
                                 "probabilities": {o: (0.8 if i == 0 else 0.2 / max(1, len(options) - 1)) for i, o in enumerate(options)}}
            else:
                top = len(question["criteria"]) - 1
                answers[name] = {"type": "score", "score": float(top - 1),
                                 "probabilities": {str(i): (0.8 if i == top - 1 else 0.2 / top) for i in range(top + 1)}}
        return DecisionResponse(model=self.model, answers=answers)
