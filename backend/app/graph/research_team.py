"""
The research team: five agents added to the main workflow.

    confirm_brief --(approve)--> research_lead <------------------------------+
                                   |   (the lead decides who works next)      |
           +-----------------------+------------+--------------+              |
           v                       v            v              v              |
    capability_analyst   component_scout x N  project_scout   reviewer -------+
           |              (one per capability,     |
           +-----> back to the lead <--in parallel)-+
                                   |
                         finish_research -> evaluate_candidates

LEARNING NOTE: who chooses the path?
    In the brief stage, the path is fixed in code. Here the LEAD AGENT chooses
    it, one decision at a time, by calling a delegation tool. The arrows below
    only say "every specialist reports back to the lead"; where the lead goes
    next is its own choice, returned as a Command (app/agents/research_lead.py).

How it plugs in
    app/graph/build.py calls `add_research_team(builder)`; confirm_brief sends
    an approved brief to ENTRY.
"""

from langgraph.graph import StateGraph

from app.agents.capability_analyst import capability_analyst
from app.agents.component_scout import component_scout
from app.agents.project_scout import project_scout
from app.agents.research_lead import research_lead
from app.agents.reviewer import reviewer

ENTRY = "research_lead"
SPECIALISTS = ("capability_analyst", "component_scout", "project_scout", "reviewer")


def add_research_team(builder: StateGraph) -> None:
    # `destinations` tells LangGraph (and the drawing) where the lead's
    # Commands may go, since the lead has no fixed outgoing edges.
    builder.add_node("research_lead", research_lead, destinations=(*SPECIALISTS, "evaluate_candidates"))
    builder.add_node("capability_analyst", capability_analyst)
    builder.add_node("component_scout", component_scout)
    builder.add_node("project_scout", project_scout)
    builder.add_node("reviewer", reviewer)
    # Every specialist reports back to the lead. When several work in
    # parallel, the lead runs once, after all of them have finished.
    for name in SPECIALISTS:
        builder.add_edge(name, "research_lead")
