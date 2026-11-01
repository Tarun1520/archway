"""
Team tools: how the research lead delegates. These are the lead's ONLY tools.

    ask_capability_analyst   break the brief into capabilities
    ask_component_scouts     search for components, one scout per capability,
                             all at the same time (optionally with the project scout)
    ask_project_scout        look for whole projects similar to the idea
    ask_reviewer             check whether the research is complete
    finish_research          end the research

LEARNING NOTE: a handoff is just a tool call
    The lead's model chooses a tool. The tool checks the choice against the
    rules below and records it as the lead's decision. The LangGraph node
    around the lead then turns that decision into a `Command`, which sends the
    run to the chosen agent (LEARNING_GUIDE.md topics 14 and 16).

The rules (enforced here, not just asked for in the prompt)
    - scouts only for capabilities that exist, at most MAX_SCOUT_ROUNDS each
    - finishing needs: capabilities recorded, each scouted, and a review newer
      than the last scouting, unless the run's model budget is nearly used up
"""

from pydantic import BaseModel, Field

from app.tools.base import Tool, ToolContext, ToolResult, refuse, reply

MAX_SCOUT_ROUNDS = 2  # how many times one capability may be scouted
MAX_PARALLEL_SCOUTS = 5
LOW_BUDGET = 4  # model calls left at which the lead may finish early


def _low_budget(ctx: ToolContext) -> bool:
    return ctx.budget.left("llm") <= LOW_BUDGET


def _decide(ctx: ToolContext, action: str, **details) -> ToolResult:
    ctx.outcome = {"action": action, **details}
    return reply({"decision": action}, terminal=True)


class InstructionsArgs(BaseModel):
    instructions: str = Field(description="A short, specific task for the agent.")


async def ask_capability_analyst(args: InstructionsArgs, ctx: ToolContext) -> ToolResult:
    return _decide(ctx, "capability_analyst", instructions=args.instructions.strip()[:600])


class AskScoutsArgs(BaseModel):
    capability_ids: list[str] = Field(description="The capabilities to search for, e.g. [\"CAP-1\", \"CAP-2\"].")
    instructions: str = Field(description="What the scouts should focus on (for a second round: the gaps to close).")
    include_project_scout: bool = Field(default=False, description="Also send the project scout at the same time.")


async def ask_component_scouts(args: AskScoutsArgs, ctx: ToolContext) -> ToolResult:
    known = {c.id for c in ctx.board.capabilities}
    if not known:
        return refuse("there are no capabilities yet; ask the capability analyst first")
    ids = list(dict.fromkeys(args.capability_ids))
    unknown = [i for i in ids if i not in known]
    if unknown:
        return refuse(f"unknown capability ids: {', '.join(unknown)}")
    priority = {c.id: c.priority for c in ctx.board.capabilities}
    # LEARNING NOTE: core first (asked for by the user, and found live)
    #   The stages of the product's central job are researched first and
    #   deepest; supporting features (accounts, storage ...) come after, once.
    core_unscouted = [c.id for c in ctx.board.capabilities if c.priority == "core" and ctx.board.scout_rounds.get(c.id, 0) == 0]
    supporting_asked = [i for i in ids if priority[i] == "supporting"]
    if supporting_asked and core_unscouted:
        return refuse(f"scout the core capabilities first ({', '.join(core_unscouted)}); "
                      f"supporting ones ({', '.join(supporting_asked)}) come after")
    spent = [i for i in ids if ctx.board.scout_rounds.get(i, 0) >= (MAX_SCOUT_ROUNDS if priority[i] == "core" else 1)]
    if spent:
        return refuse(f"no more scouting for {', '.join(spent)}: core capabilities get at most {MAX_SCOUT_ROUNDS} rounds, "
                      "supporting ones one")
    if not 1 <= len(ids) <= MAX_PARALLEL_SCOUTS:
        return refuse(f"send 1 to {MAX_PARALLEL_SCOUTS} scouts at a time")
    # A second round must close a named gap. Found live: capabilities were
    # scouted again with no open gap, costing calls and adding only filler.
    already = [i for i in ids if ctx.board.scout_rounds.get(i, 0) >= 1]
    review = ctx.board.review
    if already and review is not None:
        open_gaps = {g.capability_id for g in review.gaps}
        no_gap = [i for i in already if i not in open_gaps]
        if no_gap:
            return refuse(f"{', '.join(no_gap)} already scouted and the latest review names no gap for "
                          f"{'it' if len(no_gap) == 1 else 'them'}; scout again only where a gap is open")
    return _decide(ctx, "component_scouts", capability_ids=ids, instructions=args.instructions.strip()[:600],
                   include_project_scout=args.include_project_scout and not ctx.board.projects)


async def ask_project_scout(args: InstructionsArgs, ctx: ToolContext) -> ToolResult:
    if ctx.board.projects:
        return refuse("the project scout has already reported; similar projects are secondary")
    return _decide(ctx, "project_scout", instructions=args.instructions.strip()[:600])


async def ask_reviewer(args: InstructionsArgs, ctx: ToolContext) -> ToolResult:
    if not ctx.board.capabilities:
        return refuse("there is nothing to review yet")
    if ctx.board.review_is_fresh:
        return refuse("the latest review is still current (no scouting since); act on it or finish")
    return _decide(ctx, "reviewer", instructions=args.instructions.strip()[:600])


class FinishArgs(BaseModel):
    summary: str = Field(description="What the research found, in two or three sentences.")


async def finish_research(args: FinishArgs, ctx: ToolContext) -> ToolResult:
    if not _low_budget(ctx):
        board = ctx.board
        if not board.capabilities:
            return refuse("no capabilities have been recorded yet")
        unscouted = [c.id for c in board.capabilities if board.scout_rounds.get(c.id, 0) == 0]
        if unscouted:
            return refuse(f"these capabilities were never scouted: {', '.join(unscouted)}")
        if not board.review_is_fresh:
            return refuse("ask the reviewer to check the latest results before finishing")
    return _decide(ctx, "finish", summary=args.summary.strip()[:800])


INSTRUCTIONS_TOOL = dict(args=InstructionsArgs, terminal=True)
ASK_CAPABILITY_ANALYST = Tool(name="ask_capability_analyst",
                              description="Ask the capability analyst to break the brief into technical capabilities.",
                              run=ask_capability_analyst, **INSTRUCTIONS_TOOL)
ASK_COMPONENT_SCOUTS = Tool(name="ask_component_scouts",
                            description="Send one component scout per listed capability, in parallel.",
                            args=AskScoutsArgs, run=ask_component_scouts, terminal=True)
ASK_PROJECT_SCOUT = Tool(name="ask_project_scout",
                         description="Ask the project scout for whole projects similar to the idea (secondary).",
                         run=ask_project_scout, **INSTRUCTIONS_TOOL)
ASK_REVIEWER = Tool(name="ask_reviewer", description="Ask the reviewer to check coverage and name gaps.",
                    run=ask_reviewer, **INSTRUCTIONS_TOOL)
FINISH_RESEARCH = Tool(name="finish_research", description="End the research with a short summary.",
                       args=FinishArgs, run=finish_research, terminal=True)
