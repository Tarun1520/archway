"""
The agent loop: how every agent in Archway thinks and acts.

LEARNING NOTE: an agent is a loop (LEARNING_GUIDE.md topic 4)
    think   the model reads the conversation and asks for ONE tool
    act     our code checks the request, runs the tool, adds the result
    ...repeat, until the agent calls its "terminal" tool (its report) or
    runs out of turns.

    This file builds that loop as a small LangGraph graph with two nodes.
    Every agent uses the same loop; agents differ only in their AgentSpec:
    their instructions, their tools, and how many turns they get.

        START -> think --(asked for a tool)--> act --(not finished)--> think
                     \\--(finished / out of turns / out of budget)--> END

LEARNING NOTE: why each agent has its OWN private state
    The loop's state (`AgentLoopState`) belongs to this agent only: its own
    conversation. It is NOT shared with the main workflow. The node that runs
    an agent passes a briefing in and reads the result out. A graph that
    shared its state with the parent would hand back its whole state and
    double every append-only list (LEARNING_GUIDE.md topic 15, Lesson 24).

Guardrails, all enforced here in code
    - max turns per agent (AgentSpec.max_turns)
    - the run's model-call budget (RunBudget.take("llm") before every call)
    - only the agent's own tools can run; arguments are checked with Pydantic
    - a model reply without a tool call gets one reminder, which costs a turn
    - in its last WRAP_UP_TURNS turns an agent can only report (found live:
      scouts spent all their turns verifying and never reported)
"""

import json
import operator
from dataclasses import dataclass
from typing import Annotated, Any, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from pydantic import ValidationError

from app.agents.action_subject import action_subject
from app.graph import events
from app.llm.base import LLMClient, LLMError
from app.models.research import AgentName
from app.tools.base import Tool, ToolContext

# Model failures in a row (across agents) that stop the run instead of one agent.
MAX_MODEL_FAILURES_IN_A_ROW = 2
# In its last this-many turns, an agent is offered only its report tools.
WRAP_UP_TURNS = 2
# One model reply may ask for several tools at once (checking four packages
# is one model call, not four). More than this in one reply are ignored.
MAX_CALLS_PER_TURN = 5

@dataclass(frozen=True)
class AgentSpec:
    name: AgentName
    instructions: str  # the system prompt: who the agent is and how it works
    tools: tuple[Tool, ...]
    max_turns: int

    def tool(self, name: str) -> Tool | None:
        return next((t for t in self.tools if t.name == name), None)


class AgentLoopState(TypedDict):
    messages: Annotated[list[dict[str, Any]], operator.add]  # this agent's conversation only
    turns: int
    done: bool


@dataclass
class AgentRuntime:
    """What the loop's nodes need. Passed as LangGraph context, never saved."""

    spec: AgentSpec
    llm: LLMClient
    tools: ToolContext


def _offer(spec: AgentSpec, state: AgentLoopState) -> tuple[tuple[Tool, ...], list[dict[str, Any]]]:
    """The tools to offer this turn, and the conversation to send.

    In the last WRAP_UP_TURNS turns only the terminal (report) tools are
    offered. Two turns, not one, so a report the service rejects can be
    corrected once.
    """
    turns_left = spec.max_turns - state["turns"]
    report_tools = tuple(tool for tool in spec.tools if tool.terminal)
    if turns_left > WRAP_UP_TURNS or not report_tools or len(report_tools) == len(spec.tools):
        return spec.tools, state["messages"]
    note = (f"You have {turns_left} turn(s) left. Report now with what you have verified so far; "
            "unverified ideas can go in your notes.")
    return report_tools, [*state["messages"], {"role": "user", "content": note}]


async def think(state: AgentLoopState, runtime: Runtime[AgentRuntime]) -> dict:
    rt = runtime.context
    spec, tools = rt.spec, rt.tools
    if state["turns"] >= spec.max_turns:
        tools.notes.append(f"The {spec.name.replace('_', ' ')} ran out of turns before reporting.")
        return {"done": True}
    if not tools.budget.take("llm"):
        tools.notes.append(f"The run's model-call budget was used up while the {spec.name.replace('_', ' ')} was working.")
        return {"done": True}

    # Near the end of its turns, an agent may only report. Without this, a
    # careful agent can spend every turn verifying and lose all its work.
    # The note is added to this one request, not saved in the conversation.
    offered, messages = _offer(spec, state)
    # LEARNING NOTE: contain a failure to the agent it happened in (found live)
    #   One model call that failed after its retries used to stop the whole
    #   run. Now a single failure ends only this agent, with a visible note,
    #   and the team carries on. A SECOND failure in a row (in any agent)
    #   looks like an outage, so it is raised and the run stops, resumable.
    try:
        result = await rt.llm.chat(
            step=f"agent:{spec.name}",
            messages=[{"role": "system", "content": spec.instructions}, *messages],
            tools=[tool.spec() for tool in offered],
        )
    except LLMError as error:
        tools.budget.model_failures_in_a_row += 1
        if tools.budget.model_failures_in_a_row >= MAX_MODEL_FAILURES_IN_A_ROW:
            raise
        tools.notes.append(f"The {spec.name.replace('_', ' ')} stopped early: the model failed ({str(error)[:120]}).")
        return {"done": True}
    tools.budget.model_failures_in_a_row = 0
    tokens = None
    if result.input_tokens is not None and result.output_tokens is not None:
        tokens = result.input_tokens + result.output_tokens
    tools.emit(events.usage(service="llm", mode=rt.llm.mode, model=result.model, tokens=tokens))

    if not result.tool_calls:
        # Free text is never an answer here: every agent reports through a tool.
        # If the service rejected the call, the agent is told exactly why.
        reminder = (f"Your last tool call was rejected: {result.problem}. Call the tool again with arguments that "
                    "match its schema exactly." if result.problem else "Reply by calling one of your tools.")
        if result.problem:
            tools.emit(events.agent_action(agent=spec.name, tool="(rejected call)", ok=False))
        return {"messages": [
            {"role": "assistant", "content": result.content or ""},
            {"role": "user", "content": reminder},
        ], "turns": state["turns"] + 1}

    # LEARNING NOTE: several tool calls in one reply (LEARNING_GUIDE.md topic 54)
    #   Live, one tool per reply made a scout spend one model call on every
    #   single lookup, and the model calls (not the lookups) were the cost.
    #   Now a reply may hold several independent calls; `act` runs them in
    #   order and answers each. The model is paid for once.
    calls = result.tool_calls[:MAX_CALLS_PER_TURN]
    assistant = {"role": "assistant", "content": result.content or "", "tool_calls": [
        {"id": call.id or f"call-{i}", "type": "function", "function": {"name": call.name, "arguments": call.raw_arguments}}
        for i, call in enumerate(calls)
    ]}
    return {"messages": [assistant], "turns": state["turns"] + 1}


async def _run_one(rt: AgentRuntime, call: dict) -> tuple[str, bool]:
    """Run ONE requested tool call. Returns (the tool's reply text, whether the agent is done)."""
    name = call["function"]["name"]
    tool = rt.spec.tool(name)
    if tool is None:
        return json.dumps({"error": f"you have no tool called {name}"}), False
    subject: dict = {}  # what the call is about, for the studio (app/agents/action_subject.py)
    try:
        arguments = json.loads(call["function"]["arguments"] or "{}")
        args = tool.args.model_validate(arguments)
    except (ValueError, ValidationError) as error:
        content, done = json.dumps({"error": f"the arguments were not valid: {str(error)[:300]}"}), False
    else:
        subject = action_subject(args)
        result = await tool.run(args, rt.tools)
        content, done = result.content, result.terminal and result.ok
    rt.tools.emit(events.agent_action(agent=rt.spec.name, tool=name, ok="error" not in content[:12], **subject))
    return content, done


async def act(state: AgentLoopState, runtime: Runtime[AgentRuntime]) -> dict:
    rt = runtime.context
    replies: list[dict[str, Any]] = []
    done = False
    for call in state["messages"][-1]["tool_calls"]:
        if done:
            # The report was accepted earlier in this same reply; nothing after it runs.
            content = json.dumps({"skipped": "your report was already accepted"})
        else:
            content, done = await _run_one(rt, call)
        replies.append({"role": "tool", "tool_call_id": call["id"], "name": call["function"]["name"], "content": content})
    return {"messages": replies, "done": done}


def _after_think(state: AgentLoopState) -> str:
    if state["done"]:
        return END
    last = state["messages"][-1] if state["messages"] else {}
    return "act" if last.get("tool_calls") else "think"


def _after_act(state: AgentLoopState) -> str:
    return END if state["done"] else "think"


def build_agent_loop():
    builder = StateGraph(AgentLoopState, context_schema=AgentRuntime)
    builder.add_node("think", think)
    builder.add_node("act", act)
    builder.add_edge(START, "think")
    builder.add_conditional_edges("think", _after_think, ["act", "think", END])
    builder.add_conditional_edges("act", _after_act, ["think", END])
    return builder.compile()


AGENT_LOOP = build_agent_loop()


async def run_agent(spec: AgentSpec, briefing: str, *, llm: LLMClient, tools: ToolContext, config: RunnableConfig) -> int:
    """Run one agent to the end. Its result is left in `tools.outcome`. Returns the turns used.

    `config` is the calling node's config: passing it on makes this loop a
    child of the main run, so its progress events reach the same stream.
    """
    final = await AGENT_LOOP.ainvoke(
        {"messages": [{"role": "user", "content": briefing}], "turns": 0, "done": False},
        config,
        context=AgentRuntime(spec=spec, llm=llm, tools=tools),
    )
    return final["turns"]
