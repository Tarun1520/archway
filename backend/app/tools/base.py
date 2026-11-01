"""
What a tool is, what it may touch, and the budget every tool shares.

LEARNING NOTE: what a "tool" is for an agent (LEARNING_GUIDE.md topic 3)
    A tool is an ordinary async Python function plus a description the model
    can read. The model only REQUESTS a tool by name with arguments. The agent
    runtime (app/agents/runtime.py) checks the arguments against `args` (a
    Pydantic model), runs the function, and sends the result back.

Why the guardrails live in the tools
    The model chooses WHICH tool to call; the tool decides what is ALLOWED.
    Every tool here enforces its own rules: the run's call budget, query
    cleaning, URL safety, "you can only propose what you looked up". So no
    reply from a model, however it is worded, can get around them.

    ToolContext   what one agent's tools may read and write during one run
    RunBudget     the run's shared counters and caps (all agents together)
    ToolResult    what goes back to the model (short text), and whether the
                  call ended the agent's turn ("terminal" tools)
"""

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel

from app.integrations.factory import Integrations
from app.models.brief import ProjectBrief
from app.models.common import ServiceMode
from app.models.evidence import EvidenceItem, RepoEvidence
from app.models.research import Capability, ComponentCandidate, ReviewVerdict, SimilarProject, SourceFacts

MAX_TOOL_OUTPUT = 4_000  # characters sent back to the model per tool call


@dataclass
class RunBudget:
    """Counters shared by every agent in a run. `take` is the only way to spend.

    LEARNING NOTE: why this is safe with agents running in parallel
      asyncio runs one piece of code at a time and only switches at an
      `await`. `take` has no `await` inside, so two agents can never both
      read "one left" and both spend it.
    """

    llm_cap: int
    llm_used: int
    github_cap: int
    github_used: int
    registry_cap: int = 40  # PyPI and npm lookups (free public APIs, but be polite)
    registry_used: int = 0
    web_cap: int = 8  # documentation pages read
    web_used: int = 0
    # Model failures in a row, across all agents. One is a hiccup that costs
    # one agent its work; two in a row look like an outage that should stop
    # the run (it can be resumed from its last checkpoint).
    model_failures_in_a_row: int = 0

    def take(self, kind: str, amount: int = 1) -> bool:
        used, cap = getattr(self, f"{kind}_used"), getattr(self, f"{kind}_cap")
        if used + amount > cap:
            return False
        setattr(self, f"{kind}_used", used + amount)
        return True

    def give_back(self, kind: str, amount: int = 1) -> None:
        """Return budget that was reserved but not really spent (a cached answer cost nothing)."""
        setattr(self, f"{kind}_used", max(0, getattr(self, f"{kind}_used") - amount))

    def left(self, kind: str) -> int:
        return getattr(self, f"{kind}_cap") - getattr(self, f"{kind}_used")


@dataclass
class BoardView:
    """What the team has produced so far: what the lead and reviewer read."""

    brief: ProjectBrief
    capabilities: list[Capability] = field(default_factory=list)
    components: list[ComponentCandidate] = field(default_factory=list)
    projects: list[SimilarProject] = field(default_factory=list)
    review: ReviewVerdict | None = None
    review_is_fresh: bool = False  # True when the reviewer ran after the last scouting
    scout_rounds: dict[str, int] = field(default_factory=dict)  # capability id -> times scouted
    user_urls: list[str] = field(default_factory=list)


@dataclass
class ToolContext:
    integrations: Integrations
    budget: RunBudget
    board: BoardView
    mode: ServiceMode
    emit: Callable[[dict[str, Any]], None]
    assignment: dict[str, Any] = field(default_factory=dict)  # e.g. {"capability_id": "CAP-2"}
    # Facts about every source looked at (key: "kind:reference"), from earlier
    # agents too, so a later agent can cite what an earlier one inspected.
    facts: dict[str, SourceFacts] = field(default_factory=dict)
    # Evidence held back until something rests on it (search hits that were
    # never inspected or proposed do not clutter the evidence list).
    pending: dict[str, EvidenceItem] = field(default_factory=dict)
    # What this agent produced:
    evidence: list[EvidenceItem] = field(default_factory=list)
    repos: list[RepoEvidence] = field(default_factory=list)
    new_facts: list[SourceFacts] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    outcome: dict[str, Any] | None = None  # set by the terminal tool

    def publish(self, item: EvidenceItem) -> None:
        if all(existing.id != item.id for existing in self.evidence):
            self.evidence.append(item)

    def remember(self, facts: SourceFacts) -> None:
        key = f"{facts.kind}:{facts.reference.lower()}"
        known = self.facts.get(key)
        if known is not None and known.inspected and not facts.inspected:
            return  # never replace inspected facts with a thinner search result
        self.facts[key] = facts
        self.new_facts.append(facts)

    def known(self, kind: str, reference: str) -> SourceFacts | None:
        return self.facts.get(f"{kind}:{reference.lower()}")


@dataclass(frozen=True)
class ToolResult:
    content: str  # what the model reads (short)
    ok: bool = True
    terminal: bool = False  # True when this call ends the agent's work


def reply(data: Any, *, ok: bool = True, terminal: bool = False) -> ToolResult:
    """Turn data into the short JSON text the model reads."""
    text = json.dumps(data, ensure_ascii=False, default=str)
    if len(text) > MAX_TOOL_OUTPUT:
        text = text[:MAX_TOOL_OUTPUT] + "…(cut)"
    return ToolResult(content=text, ok=ok, terminal=terminal)


def refuse(reason: str) -> ToolResult:
    """A call that was not allowed or did not work. The model is told why."""
    return reply({"error": reason}, ok=False)


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    args: type[BaseModel]
    run: Callable[[Any, ToolContext], Awaitable[ToolResult]]
    terminal: bool = False  # calling it (successfully) ends the agent's turn

    def spec(self) -> dict[str, Any]:
        """The description the model receives, in the OpenAI "tools" format."""
        return {"type": "function", "function": {
            "name": self.name, "description": self.description, "parameters": self.args.model_json_schema(),
        }}
