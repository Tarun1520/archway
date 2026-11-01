"""
FixtureLLM: a stand-in for a language model. Free, offline, repeatable.

What this file does
    Answers the "intake" step with a brief draft worked out by simple keyword
    rules instead of a real model. Same input, same output, every time.

IMPORTANT: this is not intelligence
    It does not understand the idea. It copies sentences and looks for a few
    words. Its only jobs are to let the whole workflow run in tests, in CI
    and offline, and to make failures repeatable. Every draft it produces
    says so in its `unknowns`, and the UI shows FIXTURE MODE.

How it plugs in
    app/llm/factory.py returns this when LLM_MODE=fixture (the default).
    Tests can pass their own `responder` to script an exact reply.
"""

import json
import re
from collections.abc import Callable
from typing import Any

from app.llm.base import ChatResult, LLMError, LLMResult, ToolCall
from app.llm.fixture_agents import scripted_reply
from app.policy.clarification import QUESTION_TEXT, TOPIC_ORDER, WHY_TEXT
from app.policy.small_talk import is_small_talk
from app.policy.stated_constraints import looks_like_constraint, split_sentences

FIXTURE_NOTE = "FIXTURE MODE: this draft was produced by simple keyword rules, not by a language model."

# A responder turns (step, user text) into the JSON the "model" returns.
Responder = Callable[[str, str], dict[str, Any]]


def _first_match(text: str, patterns: dict[str, str]) -> str | None:
    """Return the label of the first pattern found in the text, or None."""
    for label, pattern in patterns.items():
        if re.search(pattern, text, re.IGNORECASE):
            return label
    return None


def _answer_for(topic: str, text: str) -> str | None:
    """Find a clarification answer written as 'Answer about <topic>: ...'."""
    match = re.search(rf"Answer about {topic}:\s*(.+)", text)
    return match.group(1).strip() if match else None


def keyword_research_plan(user_text: str) -> dict[str, Any]:
    """A research plan from the brief's own words. Not intelligence: plain keywords."""
    from app.policy.research_plan import keywords_from

    brief: dict[str, Any] = {}
    match = re.search(r"<brief>\s*(\{.*\})\s*</brief>", user_text, re.DOTALL)
    if match:
        try:
            brief = json.loads(match.group(1))
        except ValueError:
            brief = {}
    questions = []
    words = keywords_from(str(brief.get("problem", "")), 4)
    if words:
        questions.append({
            "question": "Which open-source projects already do what this brief describes?",
            "search_query": " ".join(words), "requirement_ids": [],
        })
    for item in (brief.get("must_have") or [])[:2]:
        words = keywords_from(str(item.get("text", "")), 3)
        if words:
            questions.append({
                "question": f"Which open-source projects could cover: {item.get('text', '')[:100]}",
                "search_query": " ".join(words), "requirement_ids": [item.get("id", "")],
            })
    return {"questions": questions}


def keyword_suggestions(user_text: str) -> dict[str, Any]:
    """Fixed, generic suggestions. Not intelligence: they ignore the project's subject."""
    note = "FIXTURE: a standard suggestion, not written for this project."
    unknowns: list[str] = []
    match = re.search(r"<brief>\s*(\{.*\})\s*</brief>", user_text, re.DOTALL)
    if match:
        try:
            unknowns = [str(item) for item in json.loads(match.group(1)).get("unknowns", [])]
        except ValueError:
            unknowns = []
    return {
        "must_have": [
            {"text": "Shows a clear error message when something goes wrong", "reason": note},
            {"text": "Has automated tests for its core behaviour", "reason": note},
        ],
        "nice_to_have": [{"text": "Dark mode", "reason": note}],
        "stack": [{"text": "SQLite for storage", "reason": note}],
        "constraints": [{"field": "budget", "text": "No paid services", "reason": note}],
        "assumptions": [{"text": "It is first used by a small number of people", "reason": note}],
        "unknowns": [
            {"unknown": unknown, "answers": [
                {"text": "Decide later, after the first version works", "reason": note, "add_as": "assumption"},
                {"text": "Choose the simplest option that is free to use", "reason": note, "add_as": "must_have"},
            ]}
            for unknown in unknowns[:5]
        ],
    }


def keyword_brief_draft(step: str, user_text: str) -> dict[str, Any]:
    """The default responder: a brief draft from keyword rules."""
    if step == "suggest":
        return keyword_suggestions(user_text)
    if step == "plan_research":
        return keyword_research_plan(user_text)
    if step == "draft_options":
        from app.llm.fixture_options import fixture_draft

        return fixture_draft(user_text)
    if step == "build_roadmap":
        from app.llm.fixture_plan import fixture_roadmap

        return fixture_roadmap(user_text)
    if step == "review_options":
        from app.llm.fixture_options import fixture_review

        return fixture_review(user_text)
    if step != "intake":
        raise LLMError(f"the fixture model has no scripted answer for step '{step}'")

    # Leave the clarification answers (and the prompt's markers and question
    # lines) out of the "idea" sentences.
    skipped_prefixes = ("Answer about ", "Question asked", "<user_input>", "</user_input>")
    idea_text = "\n".join(line for line in user_text.splitlines() if not line.startswith(skipped_prefixes))
    # A greeting that came before the real idea ("hi", then the project) is not
    # part of the project.
    sentences = [s for s in split_sentences(idea_text) if not is_small_talk(s)]
    describes_project = bool(sentences)
    # Sentences that read like limits belong to the constraints, not the features.
    features = [s for s in sentences if not looks_like_constraint(s)]

    deployment = _answer_for("deployment", user_text) or _first_match(idea_text, {
        "Local, on the user's own machine": r"\b(local(ly)?|offline|my (own )?(laptop|machine|computer))\b",
        "Hosted on a server": r"\b(hosted|server|cloud|from anywhere)\b",
    })
    budget = _answer_for("budget", user_text) or _first_match(idea_text, {
        "No paid services": r"no paid|for free|don'?t want to pay|free of charge",
    })
    privacy = _first_match(idea_text, {"Data stays on the user's machine": r"never leave|private|privacy|stays? local"})

    users_answer = _answer_for("users", user_text)
    multi_user: bool | None = None
    if re.search(r"\b(team|everyone|several people|multi[- ]?user|share)\b", f"{idea_text} {users_answer or ''}", re.IGNORECASE):
        multi_user = True
    elif re.search(r"\b(just for me|only me|one person|single user|my own|myself)\b", f"{idea_text} {users_answer or ''}", re.IGNORECASE):
        multi_user = False

    sensitive_answer = _answer_for("sensitive_data", user_text)
    handles_sensitive_data: bool | None = None
    if sensitive_answer is not None:
        handles_sensitive_data = not re.match(r"\s*(no|none|nope)\b", sensitive_answer, re.IGNORECASE)

    integrations_answer = _answer_for("integrations", user_text)
    mandatory_integrations: list[str] | None = None
    if integrations_answer is not None:
        is_none = re.match(r"\s*(no|none|nope|nothing)\b", integrations_answer, re.IGNORECASE)
        mandatory_integrations = [] if is_none else [integrations_answer]

    values = {
        "deployment": deployment, "users": multi_user, "sensitive_data": handles_sensitive_data,
        "budget": budget, "integrations": mandatory_integrations,
    }
    # A keyword model cannot word questions about the project. It suggests the
    # standard wording for every topic it found no value for, and the policy
    # (app/policy/clarification.py) caps and orders them.
    questions = [
        {"topic": topic, "question": QUESTION_TEXT[topic], "why_it_matters": WHY_TEXT[topic]}
        for topic in TOPIC_ORDER if values[topic] is None
    ] if describes_project else []

    if not describes_project:
        return {
            "describes_project": False, "problem": None, "users": None, "must_have": [], "nice_to_have": [],
            "stack_preferences": [], "budget": None, "privacy": None, "deployment": None, "multi_user": None,
            "handles_sensitive_data": None, "mandatory_integrations": None, "assumptions": [],
            "unknowns": [FIXTURE_NOTE], "conflicts": [], "clarifying_questions": [],
        }

    return {
        "describes_project": True,
        "problem": sentences[0][:300],
        "users": users_answer,
        "must_have": (features or sentences[:1])[:5],
        "nice_to_have": [],
        "stack_preferences": [],
        "budget": budget,
        "privacy": privacy,
        "deployment": deployment,
        "multi_user": multi_user,
        "handles_sensitive_data": handles_sensitive_data,
        "mandatory_integrations": mandatory_integrations,
        "assumptions": [],
        "unknowns": [FIXTURE_NOTE],
        "conflicts": [],
        "clarifying_questions": questions,
    }


# An agent responder turns (step, conversation) into the next tool call.
AgentResponder = Callable[[str, list[dict[str, Any]]], dict[str, Any]]


class FixtureLLM:
    mode = "fixture"

    def __init__(self, responder: Responder = keyword_brief_draft, agent_responder: AgentResponder = scripted_reply):
        self._responder = responder
        self._agent_responder = agent_responder
        self.calls: list[str] = []  # the steps asked for, so tests can count calls

    async def complete_json(self, *, step: str, system: str, user: str, schema_name: str, schema: dict[str, Any]) -> LLMResult:
        self.calls.append(step)
        return LLMResult(
            data=self._responder(step, user),
            model="fixture",
            input_tokens=None,  # a fixture has no tokens to report
            output_tokens=None,
        )

    async def chat(self, *, step: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> ChatResult:
        """A scripted agent's next move (app/llm/fixture_agents.py), as a tool call."""
        self.calls.append(step)
        try:
            move = self._agent_responder(step, messages)
        except KeyError as error:
            raise LLMError(str(error)) from error
        # A scripted move may be a list: several tool calls in one reply.
        moves = move if isinstance(move, list) else [move]
        calls = [
            ToolCall(id=f"fixture-{len(self.calls)}-{i}", name=m["name"], arguments=m["arguments"],
                     raw_arguments=json.dumps(m["arguments"]))
            for i, m in enumerate(moves)
        ]
        return ChatResult(content=None, tool_calls=calls, model="fixture", input_tokens=None, output_tokens=None)
