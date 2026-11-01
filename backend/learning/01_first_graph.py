"""
Lesson 01: Your first LangGraph graph
=====================================

What you learn here
    The three building blocks of every LangGraph program:
      1. STATE  - one shared dictionary that every step can read.
      2. NODES  - plain Python functions. Each one is a step.
      3. EDGES  - arrows that say which node runs next.

How to run (from the project root)
    backend/.venv/bin/python backend/learning/01_first_graph.py

Where Archway uses this
    The whole workflow in IMPLEMENTATION_GUIDE.md Section 5 is one big graph
    built exactly like this one: intake -> confirm_brief -> plan_research ...
"""

from typing import TypedDict

from langgraph.graph import END, START, StateGraph


# -----------------------------------------------------------------------------
# 1. STATE
# -----------------------------------------------------------------------------
# LEARNING NOTE: what is "state"?
#   State is the graph's memory while it runs. It is a dictionary with a fixed
#   set of keys. A TypedDict is just a normal dict plus a description of which
#   keys exist and what type each value has, so your editor can catch typos.
class State(TypedDict):
    idea: str  # what the user typed
    word_count: int  # filled in by the first node
    summary: str  # filled in by the second node


# -----------------------------------------------------------------------------
# 2. NODES
# -----------------------------------------------------------------------------
# LEARNING NOTE: the node contract
#   A node receives the CURRENT state and returns a dictionary containing ONLY
#   the keys it wants to change. LangGraph merges that small dictionary into
#   the state for you. A node never has to copy the whole state.
def count_words(state: State) -> dict:
    """Step 1: count the words in the idea."""
    return {"word_count": len(state["idea"].split())}


def summarise(state: State) -> dict:
    """Step 2: build a one-line summary. It can read what step 1 wrote."""
    return {"summary": f"{state['word_count']} words about: {state['idea']}"}


# -----------------------------------------------------------------------------
# 3. EDGES (and putting it together)
# -----------------------------------------------------------------------------
def build_graph():
    """Describe the graph, then compile it into something we can run."""
    # LEARNING NOTE: builder vs graph
    #   StateGraph(State) is a *builder*: a description that is still editable.
    #   .compile() checks the description (for example, that no node is
    #   unreachable) and returns the runnable graph.
    builder = StateGraph(State)

    # Register the nodes. The string is the node's name; names are what you
    # see in logs, in streamed events, and in the workflow view in the UI.
    builder.add_node("count_words", count_words)
    builder.add_node("summarise", summarise)

    # START and END are two special built-in markers, not real nodes.
    builder.add_edge(START, "count_words")  # where a run begins
    builder.add_edge("count_words", "summarise")  # then this
    builder.add_edge("summarise", END)  # where a run finishes

    return builder.compile()


if __name__ == "__main__":
    graph = build_graph()

    # LEARNING NOTE: invoke
    #   .invoke(input) runs the graph from START to END and returns the final
    #   state. The input only needs the keys the first node reads.
    final_state = graph.invoke({"idea": "a notes app with semantic search"})

    print("Final state:")
    for key, value in final_state.items():
        print(f"  {key}: {value!r}")

    # LangGraph can describe its own shape as a Mermaid diagram. Paste the
    # text below into https://mermaid.live to see the picture.
    print("\nThe graph as a Mermaid diagram:")
    print(graph.get_graph().draw_mermaid())
