"""
Lesson 07: How an agent works (the model-and-tools loop)
========================================================

What you learn here
    An "agent" is not magic. It is a LOOP:
      1. Give the model the conversation so far.
      2. The model replies with EITHER a final answer OR a request such as
         "please call the tool search_github with query='markdown notes'".
      3. If it asked for a tool, YOUR code runs the tool and adds the result
         to the conversation. Go back to 1.
      4. If it gave a final answer, stop.
    The model never runs anything itself. It only writes text that asks.

    This lesson uses a FAKE model (a small Python function with a script), so
    it runs offline, costs nothing, and behaves the same every time. A real
    model would slot into the same place.

How to run (from the project root)
    backend/.venv/bin/python backend/learning/07_agent_tool_loop.py

Where Archway uses this
    Archway is mostly a WORKFLOW (the path is drawn by us, in the graph), not
    a free-roaming agent (where the model picks the path). Knowing the loop
    still matters: it is how any tool-using model step works, and it shows
    why limits and rules belong in your code rather than in the model.
"""

from typing import Annotated, Literal, TypedDict

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, ToolMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

MAX_MODEL_TURNS = 4  # our own hard limit on the loop


# -----------------------------------------------------------------------------
# State: the conversation
# -----------------------------------------------------------------------------
# LEARNING NOTE: message types
#   HumanMessage = what the user said
#   AIMessage    = what the model said (may contain tool_calls)
#   ToolMessage  = the result of running a tool, sent back to the model
#   `add_messages` is a ready-made reducer that appends new messages.
class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    model_turns: int


# -----------------------------------------------------------------------------
# A tool: an ordinary function the model is allowed to ask for
# -----------------------------------------------------------------------------
def search_github(query: str) -> str:
    """Pretend GitHub search. FIXTURE DATA: these repositories are made up."""
    return "FIXTURE RESULT: example/notes-md (MIT, 1200 stars); example/md-vault (license not retrieved)"


TOOLS = {"search_github": search_github}  # name -> function


# -----------------------------------------------------------------------------
# The fake model
# -----------------------------------------------------------------------------
def fake_model(messages: list[AnyMessage]) -> AIMessage:
    """Stands in for a real LLM. Scripted: search first, then answer."""
    has_tool_result = any(isinstance(message, ToolMessage) for message in messages)

    if not has_tool_result:
        # A real model produces this structure when it decides it needs a tool.
        # Note it is only a REQUEST: a name, some arguments, and an id.
        return AIMessage(
            content="",
            tool_calls=[{"name": "search_github", "args": {"query": "markdown notes"}, "id": "call_1"}],
        )

    tool_text = [m.content for m in messages if isinstance(m, ToolMessage)][-1]
    return AIMessage(content=f"I found two candidates. One has no license on record, so it needs review. ({tool_text})")


# -----------------------------------------------------------------------------
# Nodes
# -----------------------------------------------------------------------------
def call_model(state: State) -> dict:
    reply = fake_model(state["messages"])
    return {"messages": [reply], "model_turns": state["model_turns"] + 1}


def run_tools(state: State) -> dict:
    """Run every tool the model asked for and report the results back."""
    last_message = state["messages"][-1]
    results = []
    for call in last_message.tool_calls:
        # LEARNING NOTE: this lookup is a security boundary.
        #   The model can only trigger functions that WE put in TOOLS.
        #   If it asks for anything else, we say no instead of obeying.
        tool = TOOLS.get(call["name"])
        output = tool(**call["args"]) if tool else f"Error: no tool named {call['name']}"
        # tool_call_id links this result to the request it answers.
        results.append(ToolMessage(content=output, tool_call_id=call["id"]))
    return {"messages": results}


def route_after_model(state: State) -> Literal["run_tools", "__end__"]:
    """The loop decision: tools requested and budget left? Otherwise stop."""
    last_message = state["messages"][-1]
    wants_tool = bool(getattr(last_message, "tool_calls", None))
    if wants_tool and state["model_turns"] < MAX_MODEL_TURNS:
        return "run_tools"
    return END  # END is the string "__end__"


def build_graph():
    builder = StateGraph(State)
    builder.add_node("call_model", call_model)
    builder.add_node("run_tools", run_tools)
    builder.add_edge(START, "call_model")
    builder.add_conditional_edges("call_model", route_after_model)
    builder.add_edge("run_tools", "call_model")  # <- this edge is the loop
    return builder.compile()


if __name__ == "__main__":
    question = HumanMessage(content="Find open-source markdown note apps I could reuse.")
    final = build_graph().invoke({"messages": [question], "model_turns": 0})

    print("The whole conversation, in order:\n")
    for message in final["messages"]:
        kind = type(message).__name__
        if isinstance(message, AIMessage) and message.tool_calls:
            call = message.tool_calls[0]
            print(f"  {kind:13} asks for tool: {call['name']}({call['args']})")
        else:
            print(f"  {kind:13} {message.content}")
    print(f"\nModel turns used: {final['model_turns']} of {MAX_MODEL_TURNS}")
