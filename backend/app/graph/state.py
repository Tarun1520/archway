"""
The workflow's shared state: the memory every node reads and updates.

LEARNING NOTE: state versus context
    STATE (this file) is what the workflow PRODUCES. It changes as nodes run
    and the checkpointer saves it after every step.
    CONTEXT (context.py) is settings for one run that nodes only read.

LEARNING NOTE: why plain dicts and lists, not Pydantic objects?
    The checkpointer has to write the state to disk after every step. Plain
    JSON-like data (text, numbers, lists, dicts) always saves and loads
    cleanly. So the brief is kept here as a dict, and each node turns it into
    a ProjectBrief object when it needs to work with it.

LEARNING NOTE: reducers (LEARNING_GUIDE.md topic 8)
    `Annotated[list[str], operator.add]` means "append new items to the
    list". Keys without a reducer are simply replaced by the newest value.
"""

import operator
from typing import Annotated, Any, TypedDict


class WorkflowState(TypedDict):
    run_id: str

    # Everything the user has said: the idea, then any clarification answers.
    # Appended to, never replaced.
    user_texts: Annotated[list[str], operator.add]

    # The current ProjectBrief as a dict (None until intake has run).
    brief: dict[str, Any] | None

    # Questions waiting for the user (each is a ClarifyQuestion as a dict).
    open_questions: list[dict[str, Any]]
    # Topics already asked, so no topic is ever asked twice.
    asked_topics: Annotated[list[str], operator.add]
    # The questions themselves (each a {"topic", "question"} dict). An answer
    # like "No" only makes sense next to the question it answers.
    asked_questions: Annotated[list[dict[str, Any]], operator.add]
    # The user's answers, each a {"topic", "answer"} dict, so the studio can
    # show the questions step again later exactly as it was answered.
    answered_questions: Annotated[list[dict[str, Any]], operator.add]
    # Topics the user skipped; each one becomes a visible assumption.
    assumed_topics: Annotated[list[str], operator.add]
    # How many times the clarify step has run (limited in nodes/intake.py).
    clarify_rounds: int

    # The call counter for the per-run cap (LEARNING_GUIDE.md topic 19).
    llm_calls: int

    # True once the user has approved a brief version.
    brief_confirmed: bool

    # --- The research team's shared board (Phase 3) -------------------------------
    # LEARNING NOTE: this is how the agents share their work. Each agent reads
    # the board, does its job with its tools, and writes its result back here.
    # Lists that several agents add to AT THE SAME TIME (parallel scouts) use
    # an append reducer; values written by one agent at a time are replaced.
    capabilities: list[dict[str, Any]]  # written by the capability analyst
    components: Annotated[list[dict[str, Any]], operator.add]  # component scouts
    projects: Annotated[list[dict[str, Any]], operator.add]  # the project scout
    review: dict[str, Any] | None  # the reviewer
    team_messages: Annotated[list[dict[str, Any]], operator.add]  # tasks and reports
    source_facts: Annotated[list[dict[str, Any]], operator.add]  # facts the tools retrieved
    scout_rounds: Annotated[list[str], operator.add]  # one capability id per finished scouting job
    repos: Annotated[list[dict[str, Any]], operator.add]  # inspected repositories (RepoEvidence)
    evidence: Annotated[list[dict[str, Any]], operator.add]  # EvidenceItem
    research_notes: Annotated[list[str], operator.add]  # visible explanations of anything partial
    lead_turns: int  # how many decisions the research lead has made
    research_finished: bool
    # Phase 4: eligibility and decisions (written once by evaluate_candidates)
    eligibility: list[dict]
    receipts: list[dict]
    jev_calls: int
    decisions_finished: bool

    # --- Options (Phase 5) ------------------------------------------------------------
    # Older saved runs do not have these keys: nodes read them with .get().
    options_requested: bool  # the person asked for options (set after research, by the service)
    options: list[dict[str, Any]]  # EVERY version of every option, oldest first (a revision adds the next version)
    option_retries: int  # redrafts after a failed review, in this round (limit: nodes/review_options.py)
    option_feedback: dict[str, list[str]]  # option id -> what failed review, for a redraft
    option_problems: dict[str, list[str]]  # "id@version" -> problems found while building it
    revision: dict[str, Any] | None  # {"option_id": ... | None, "request": ...} while a change is being drafted
    selected_option_id: str | None
    approved_option: dict[str, Any] | None  # {"id", "version"}: approval belongs to ONE version
    options_notes: Annotated[list[str], operator.add]  # visible explanations: what failed, what was not checked
    no_recommendation: bool

    # --- The build plan (Phase 6) -------------------------------------------------------
    # Started by the person after approving an option version (a button; the service then sets `plan_requested`).
    plan_requested: bool
    roadmap: dict[str, Any] | None  # Roadmap: tasks in build order and the decision records
    plan_issues: list[str]  # what the checks found; sent back to the planner once (the retry)
    plan_retries: int  # how many times the roadmap was redrafted after failed checks (limit: nodes/check_prompts.py)
    plan_files: list[dict[str, Any]]  # PromptFile: every file of the pack, with each prompt's rubric
    plan_links: list[dict[str, Any]]  # PlanLink: requirement -> tasks -> components -> verdicts -> evidence
    plan_passed: bool | None  # every check passed (None until checked)
    plan_outcome: str | None  # "full", or "partial" when checks still fail after the retry
    plan_notes: list[str]  # visible explanations: what was dropped, what failed (replaced, so a new plan starts clean)
    plan_export: dict[str, Any] | None  # the whole plan as JSON (app/promptgen/export.py)


def initial_state(run_id: str, user_texts: list[str]) -> WorkflowState:
    """The state a brand-new run starts with."""
    return WorkflowState(
        run_id=run_id,
        user_texts=user_texts,
        brief=None,
        open_questions=[],
        asked_topics=[],
        asked_questions=[],
        answered_questions=[],
        assumed_topics=[],
        clarify_rounds=0,
        llm_calls=0,
        brief_confirmed=False,
        capabilities=[],
        components=[],
        projects=[],
        review=None,
        team_messages=[],
        source_facts=[],
        scout_rounds=[],
        repos=[],
        evidence=[],
        research_notes=[],
        lead_turns=0,
        research_finished=False,
        eligibility=[],
        receipts=[],
        jev_calls=0,
        decisions_finished=False,
        options_requested=False,
        options=[],
        option_retries=0,
        option_feedback={},
        option_problems={},
        revision=None,
        selected_option_id=None,
        approved_option=None,
        options_notes=[],
        no_recommendation=False,
        plan_requested=False,
        roadmap=None,
        plan_issues=[],
        plan_retries=0,
        plan_files=[],
        plan_links=[],
        plan_passed=None,
        plan_outcome=None,
        plan_notes=[],
        plan_export=None,
    )
