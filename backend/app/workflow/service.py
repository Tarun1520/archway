"""
WorkflowService: the bridge between the API and the LangGraph workflow.

What this file does
    - starts a run, or resumes it with the user's reply
    - listens to the graph while it works (LangGraph's stream)
    - SAVES what it hears: progress events, brief versions, usage counts
    - builds a snapshot of a run so the UI can redraw it from nothing

Why saving happens here and not inside the nodes
    Nodes stay pure: state in, changes out, no database. That keeps them easy
    to read and test. This one file does all the recording.

How a run is identified
    The run's id is used as LangGraph's `thread_id` (LEARNING_GUIDE.md topic
    10), so "run 4f2a" in Archway's tables and "thread 4f2a" in the
    checkpoint file are the same thing.

How it plugs in
    app/main.py creates one WorkflowService at start-up.
    app/api/workflow.py calls start / answer_clarify / decide_confirm /
    snapshot.
"""

import asyncio
import logging
from typing import Any

import aiosqlite
from langgraph.types import Command

from app.config.settings import Settings
from app.auth.quota import tokens_left
from app.auth.quota_llm import QUOTA_MESSAGE, QuotaLLM
from app.db import briefs_repo, messages_repo, options_repo, plans_repo, research_repo, run_events_repo, runs_repo, usage_repo, users_repo
from app.db.connection import open_connection
from app.decisions.client import DecisionClient
from app.decisions.factory import build_decision_client
from app.graph.context import RunContext
from app.policy.eligibility import EligibilityPolicy
from app.policy.idea_readiness import idea_readiness
from app.graph.state import initial_state
from app.llm.base import LLMClient, LLMError
from app.models.brief import ProjectBrief
from app.models.common import utc_now
from app.integrations.factory import Integrations
from app.models.evidence import EvidenceItem, RepoEvidence
from app.models.lifecycle import RunStatus
from app.models.research import Capability, ComponentCandidate, ReviewVerdict, SimilarProject, TeamMessage
from app.models.run import RunStatusChange
from app.tools.base import RunBudget
from app.models.usage import UsageEvent
from app.models.option_flow import ApprovalDecision, OptionDecision, VersionRef
from app.models.workflow import AskedQuestion, ClarifyAnswer, ConfirmDecision, RunSnapshot, UsageCount, WaitingFor
from app.options.versions import presented

logger = logging.getLogger("archway.workflow")


class WorkflowConflict(Exception):
    """The request does not fit the run's current state. The API answers HTTP 409."""


class WorkflowService:
    def __init__(self, *, graph, settings: Settings, llm: LLMClient, integrations: Integrations | None = None,
                 decisions: DecisionClient | None = None):
        self._graph = graph
        self._settings = settings
        self._llm = llm
        self._integrations = integrations
        self._decisions = decisions or build_decision_client(settings)
        # Research runs in the background (see decide_confirm). Keeping a
        # reference stops Python from discarding a task that is still running.
        self._tasks: set[asyncio.Task] = set()
        # One lock per run, so two requests can never drive the same run at once.
        self._locks: dict[str, asyncio.Lock] = {}

    # --- Small helpers --------------------------------------------------------
    def _config(self, run_id: str) -> dict:
        return {"configurable": {"thread_id": run_id}}

    def _lock(self, run_id: str) -> asyncio.Lock:
        return self._locks.setdefault(run_id, asyncio.Lock())

    async def _waiting_for(self, run_id: str) -> tuple[WaitingFor | None, bool, bool]:
        """Returns (what the run is paused on, whether it exists, whether it finished)."""
        state = await self._graph.aget_state(self._config(run_id))
        exists = state.created_at is not None
        finished = exists and not state.next

        for task in state.tasks:
            for pause in task.interrupts:
                payload = dict(pause.value)
                return WaitingFor(node=payload.pop("node"), payload=payload), exists, finished
        return None, exists, finished

    # --- Starting and resuming ------------------------------------------------
    async def start(self, run_id: str) -> None:
        """Begin a new run, or continue one that stopped on an error."""
        waiting, exists, finished = await self._waiting_for(run_id)
        if waiting is not None:
            raise WorkflowConflict(f"this run is waiting for you at the '{waiting.node}' step")
        if finished:
            raise WorkflowConflict("this run has already finished")

        if exists:
            # A saved checkpoint with work left: continue from where it stopped.
            # Passing None means "no new input, carry on".
            await self._drive(run_id, None, "run_resumed")
            return

        async with open_connection(self._settings.database_path) as db:
            run = await runs_repo.get_run(db, run_id)
            messages = await messages_repo.list_messages(db, run.project_id)
        user_texts = [message.content for message in messages if message.role == "user"]
        if not user_texts:
            raise WorkflowConflict("describe your idea first: this project has no messages yet")
        # Not enough to draft a brief from (only a greeting, or only "an app"):
        # refuse, with the same reason the studio shows (app/policy/idea_readiness.py).
        readiness = idea_readiness(user_texts)
        if not readiness.ready:
            raise WorkflowConflict(readiness.reason or "describe your idea first")

        await self._drive(run_id, initial_state(run_id, user_texts), "run_started")

    async def answer_clarify(self, run_id: str, answer: ClarifyAnswer) -> None:
        waiting, _, _ = await self._waiting_for(run_id)
        if waiting is None or waiting.node != "clarify":
            raise WorkflowConflict("this run is not waiting for answers to questions")

        asked = [question["topic"] for question in waiting.payload["questions"]]
        if "idea" in asked and not answer.answers.get("idea", "").strip():
            # There is nothing to assume about a project that has not been
            # described, so this question cannot be skipped.
            raise WorkflowConflict("tell Archway what you would like to build to continue")
        unanswered = [topic for topic in asked if not answer.answers.get(topic, "").strip()]
        if unanswered and not answer.continue_with_assumptions:
            raise WorkflowConflict(
                f"answer every question or choose 'Continue with assumptions' (unanswered: {', '.join(unanswered)})"
            )
        await self._drive(run_id, Command(resume=answer.model_dump(mode="json")), "run_resumed")

    async def decide_confirm(self, run_id: str, decision: ConfirmDecision) -> None:
        waiting, _, _ = await self._waiting_for(run_id)
        if waiting is None or waiting.node != "confirm_brief":
            raise WorkflowConflict("this run is not waiting for a brief to be confirmed")
        if decision.action == "edit" and decision.edit is None:
            raise WorkflowConflict("an edit must include the edited brief")
        graph_input = Command(resume=decision.model_dump(mode="json"))
        await self._drive_maybe_in_background(run_id, graph_input, "run_resumed", long_running=decision.action == "approve")

    async def _drive_maybe_in_background(self, run_id: str, graph_input: Any, first_event: str, *, long_running: bool) -> None:
        """Drive the graph now, or (for work that takes minutes) as a background task and answer at once.

        LEARNING NOTE: why in the background?
          Approving a brief starts the research team, and asking for options starts a drafting and review loop:
          both can work for a long time. Holding a web request open that long is fragile, so the run is started
          as a background task and the request returns at once. The browser follows progress through the event
          stream, as always. (Tests turn background work off so each request finishes its work.)
        """
        if long_running and self._settings.background_research:
            if self._lock(run_id).locked():
                raise WorkflowConflict("this run is already working; wait for it to pause")
            task = asyncio.create_task(self._drive(run_id, graph_input, first_event))
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)
            await asyncio.sleep(0)  # let the task take the run's lock before answering
            return
        await self._drive(run_id, graph_input, first_event)

    # --- Phase 5: options -------------------------------------------------------------
    async def _finished_values(self, run_id: str) -> dict[str, Any]:
        """The saved state of a run that has stopped (nothing running, nothing waiting), or a conflict."""
        waiting, exists, finished = await self._waiting_for(run_id)
        if self.is_running(run_id):
            raise WorkflowConflict("this run is already working; wait for it to pause")
        if waiting is not None:
            raise WorkflowConflict(f"this run is waiting for you at the '{waiting.node}' step")
        if not exists or not finished:
            raise WorkflowConflict("this run has not reached the end of its research yet")
        return (await self._graph.aget_state(self._config(run_id))).values or {}

    async def request_options(self, run_id: str) -> None:
        """The person asked for architecture options after the shortlist."""
        waiting, exists, finished = await self._waiting_for(run_id)
        values = (await self._graph.aget_state(self._config(run_id))).values or {} if exists else {}
        if exists and not finished and values.get("options_requested") and waiting is None and not self.is_running(run_id):
            await self._drive_maybe_in_background(run_id, None, "run_resumed", long_running=True)  # drafting stopped on an error: carry on
            return
        values = await self._finished_values(run_id)
        if not values.get("decisions_finished"):
            raise WorkflowConflict("options can be drafted once the research and its decisions have finished")
        if values.get("options_requested"):
            raise WorkflowConflict("options have already been drafted for this run")
        # LEARNING NOTE: update_state(as_node=...) says "pretend this node just finished with these changes",
        #   so the graph works out the next step from its CURRENT arrows. That is how a run that already stopped at
        #   the shortlist (saved before the options stage existed) can carry on into it.
        await self._graph.aupdate_state(self._config(run_id), {"options_requested": True}, as_node="evaluate_candidates")
        async with open_connection(self._settings.database_path) as db:
            await options_repo.mark_requested(db, run_id)
        await self._drive_maybe_in_background(run_id, None, "options_started", long_running=True)

    async def decide_options(self, run_id: str, decision: OptionDecision) -> None:
        waiting, _, _ = await self._waiting_for(run_id)
        if waiting is None or waiting.node != "select_or_revise":
            raise WorkflowConflict("this run is not waiting for an option to be chosen")
        offered = [item["id"] for item in waiting.payload.get("presented", [])]
        if decision.action == "select" and decision.option_id not in offered:
            raise WorkflowConflict(f"{decision.option_id} is not one of the options on offer")
        if decision.action == "revise":
            if decision.option_id and decision.option_id not in offered:
                raise WorkflowConflict(f"{decision.option_id} is not one of the options on offer")
            if not decision.option_id and len(offered) == 1:
                decision = decision.model_copy(update={"option_id": offered[0]})  # only one on offer: the change is for it
            elif not decision.option_id and len(offered) > 1:
                raise WorkflowConflict("say which option the change is for")
        await self._drive_maybe_in_background(
            run_id, Command(resume=decision.model_dump(mode="json")), "run_resumed", long_running=decision.action == "revise",
        )

    async def decide_approval(self, run_id: str, decision: ApprovalDecision) -> None:
        waiting, _, _ = await self._waiting_for(run_id)
        if waiting is None or waiting.node != "approve_version":
            raise WorkflowConflict("this run is not waiting for an approval")
        await self._drive_maybe_in_background(
            run_id, Command(resume=decision.model_dump(mode="json")), "run_resumed", long_running=decision.action == "change",
        )

    async def request_change(self, run_id: str, option_id: str, request: str) -> None:
        """A change to an option after approval: the NEXT VERSION is drafted and reviewed; approval does not carry over."""
        values = await self._finished_values(run_id)
        approved = values.get("approved_option")
        if not approved or approved["id"] != option_id:
            raise WorkflowConflict("only the approved option can be changed this way")
        await self._graph.aupdate_state(
            self._config(run_id),
            {"revision": {"option_id": option_id, "request": request.strip()}, "approved_option": None, "selected_option_id": None, "option_retries": 0,
             "plan_requested": False},  # a plan made for the old version is now stale; a new one is asked for again
            as_node="evaluate_candidates",
        )
        await self._drive_maybe_in_background(run_id, None, "run_resumed", long_running=True)

    # --- Phase 6: the build plan ----------------------------------------------------------
    async def request_plan(self, run_id: str) -> None:
        """The person asked for the build plan (roadmap and prompt pack) for the approved option version."""
        waiting, exists, finished = await self._waiting_for(run_id)
        values = (await self._graph.aget_state(self._config(run_id))).values or {} if exists else {}
        if exists and not finished and values.get("plan_requested") and waiting is None and not self.is_running(run_id):
            await self._drive_maybe_in_background(run_id, None, "run_resumed", long_running=True)  # planning stopped on an error: carry on
            return
        values = await self._finished_values(run_id)
        approved = values.get("approved_option")
        if not approved:
            raise WorkflowConflict("approve one option version before asking for the build plan")
        built = (values.get("roadmap") or {}).get("architecture")
        if values.get("plan_requested") and values.get("plan_export") and built == approved:
            raise WorkflowConflict(f"the build plan for {approved['id']} version {approved['version']} has already been made")
        # LEARNING NOTE: as in request_options, update_state(as_node=...) lets the graph pick the next step from its
        #   arrows: approve_version's edge sends a run with `plan_requested` to build_roadmap. Every plan key is reset,
        #   so a plan for a newer approved version starts clean.
        await self._graph.aupdate_state(self._config(run_id), {
            "plan_requested": True, "roadmap": None, "plan_issues": [], "plan_retries": 0, "plan_files": [], "plan_links": [],
            "plan_passed": None, "plan_outcome": None, "plan_notes": [], "plan_export": None,
        }, as_node="approve_version")
        async with open_connection(self._settings.database_path) as db:
            await plans_repo.start_plan(db, run_id, VersionRef.model_validate(approved))
            run = await runs_repo.get_run(db, run_id)
            if run.status == RunStatus.AWAITING_SELECTION:
                await runs_repo.change_status(db, run_id, RunStatusChange(status=RunStatus.BUILDING_PLAN))
        await self._drive_maybe_in_background(run_id, None, "plan_started", long_running=True)

    def is_running(self, run_id: str) -> bool:
        return self._lock(run_id).locked()

    def running_runs(self) -> set[str]:
        """The ids of every run that is working right now (for the admin dashboard)."""
        return {run_id for run_id, lock in self._locks.items() if lock.locked()}

    async def shutdown(self) -> None:
        """Stop background research before the databases close.

        LEARNING NOTE: cancelling is safe here. The checkpointer saved the run
        after its last finished step, so "Start" carries on from there later.
        """
        for task in list(self._tasks):
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)

    # --- Driving the graph and recording what happens --------------------------
    async def _drive(self, run_id: str, graph_input: Any, first_event: str) -> None:
        """Run the graph until it pauses or ends, saving everything it reports."""
        lock = self._lock(run_id)
        if lock.locked():
            raise WorkflowConflict("this run is already working; wait for it to pause")

        async with lock, open_connection(self._settings.database_path) as db:
            await run_events_repo.add_event(db, run_id, first_event, {})
            # The run's budget starts from what it has ALREADY used (saved usage
            # rows), so stopping and resuming can never reset the caps.
            used = await usage_repo.calls_by_service(db, run_id)
            budget = RunBudget(
                llm_cap=self._settings.max_llm_calls_per_run, llm_used=used.get("llm", 0),
                github_cap=self._settings.github_calls_cap, github_used=used.get("github", 0),
            )
            # The owner's monthly token quota: a run that starts with nothing left stops at once; otherwise the model
            # client counts down what is left (app/auth/quota_llm.py).
            llm = self._llm
            left = await self._quota_left(db, run_id)
            if left is not None:
                if left <= 0:
                    await run_events_repo.add_event(db, run_id, "run_error", {"message": QUOTA_MESSAGE})
                    return
                llm = QuotaLLM(self._llm, left)
            context = RunContext(
                llm=llm, max_llm_calls=self._settings.max_llm_calls_per_run,
                integrations=self._integrations, budget=budget,
                decisions=self._decisions, max_jev_calls=self._settings.max_jev_calls_per_run,
                eligibility_policy=EligibilityPolicy(licenses=self._settings.license_policy,
                                                     exclude_archived=self._settings.exclude_archived),
            )
            try:
                # LEARNING NOTE: two stream modes at once (LEARNING_GUIDE topic 12)
                #   "custom"  = what nodes announce while working
                #   "updates" = which node finished and what it changed
                #   subgraphs=True: also hear what happens INSIDE each agent's
                #   own loop (its tool use), not only when the agent finishes.
                async for part in self._graph.astream(
                    graph_input, self._config(run_id), context=context,
                    stream_mode=["updates", "custom"], subgraphs=True, version="v2",
                ):
                    if part["type"] == "custom":
                        await self._record_custom(db, run_id, part["data"])
                    elif not part["ns"]:  # only the main workflow's steps change the saved run
                        await self._record_updates(db, run_id, part["data"])
            except LLMError as error:
                # A model problem is reported, not hidden. The run keeps its
                # last checkpoint, so "start" can be pressed again.
                logger.warning("model call failed", extra={"fields": {"run_id": run_id, "reason": str(error)}})
                await run_events_repo.add_event(db, run_id, "run_error", {"message": str(error)})
                return
            except Exception:
                logger.exception("workflow failed", extra={"fields": {"run_id": run_id}})
                await run_events_repo.add_event(
                    db, run_id, "run_error", {"message": "The workflow stopped on an unexpected error. See the backend log."}
                )
                return

            _, _, finished = await self._waiting_for(run_id)
            if finished:
                research = await research_repo.get_snapshot(db, run_id)
                options = await options_repo.get_snapshot(db, run_id)
                plan = await plans_repo.get_snapshot(db, run_id, options.approved)
                if plan.outcome and not plan.stale and plan.built_for:
                    message = (f"Build plan ready for {plan.built_for.id} version {plan.built_for.version}"
                               + (": every prompt passed its checks." if plan.passed else " (PARTIAL: some checks did not pass, see the notes)."))
                elif options.approved:
                    message = f"Option {options.approved.id} version {options.approved.version} approved."
                elif research.finished:
                    message = (
                        f"Research finished: {len(research.capabilities)} capabilities, "
                        f"{len(research.components)} candidate components, {len(research.projects)} similar projects"
                        + (" (partial: see the notes)" if research.notes else "")
                        + ". Decisions and eligibility are on each component."
                    )
                else:
                    message = "Brief confirmed."
                await run_events_repo.add_event(db, run_id, "workflow_finished", {"message": message})

    async def _quota_left(self, db: aiosqlite.Connection, run_id: str) -> int | None:
        """Model tokens the run's owner has left this month (None = no limit, or accounts switched off)."""
        if not self._settings.auth_enabled:
            return None
        cursor = await db.execute(
            "SELECT projects.owner_id AS owner FROM runs JOIN projects ON projects.id = runs.project_id WHERE runs.id = ?", (run_id,))
        row = await cursor.fetchone()
        if row is None or row["owner"] is None:
            return None
        return await tokens_left(db, await users_repo.get_user(db, row["owner"]))

    async def _record_custom(self, db: aiosqlite.Connection, run_id: str, data: dict) -> None:
        """Save one event a node announced."""
        data = dict(data)
        name = data.pop("event")
        if name == "usage":
            await usage_repo.add_usage(db, UsageEvent(
                run_id=run_id, service=data["service"], mode=data["mode"], count=1,
                tokens_if_known=data.get("tokens"), timestamp=utc_now(),
            ))
        await run_events_repo.add_event(db, run_id, name, data)

    async def _record_updates(self, db: aiosqlite.Connection, run_id: str, data: dict) -> None:
        """Save what a finished node changed, or that the run has paused."""
        for node, changes in data.items():
            if node == "__interrupt__":
                # The run paused for the user. `changes` holds the pause(s).
                for pause in changes:
                    await run_events_repo.add_event(db, run_id, "node_waiting", {"node": pause.value["node"]})
                    if pause.value["node"] == "select_or_revise":
                        run = await runs_repo.get_run(db, run_id)
                        if run.status == RunStatus.RESEARCHING:
                            await runs_repo.change_status(db, run_id, RunStatusChange(status=RunStatus.AWAITING_SELECTION))
                continue

            if isinstance(changes, dict):
                if changes.get("brief"):
                    brief = ProjectBrief.model_validate(changes["brief"])
                    await briefs_repo.save_brief(db, run_id, brief)
                    await run_events_repo.add_event(db, run_id, "brief_updated", {
                        "version": brief.version, "confirmed": brief.confirmed, "conflicts": len(brief.conflicts),
                    })
                if changes.get("brief_confirmed"):
                    # From here on the lifecycle rules allow research to start,
                    # and the graph is about to start it.
                    await runs_repo.mark_brief_confirmed(db, run_id)
                    run = await runs_repo.get_run(db, run_id)
                    if run.status == RunStatus.DRAFT:
                        await runs_repo.change_status(db, run_id, RunStatusChange(status=RunStatus.RESEARCHING))
                await self._record_research(db, run_id, node, changes)
                await self._record_options(db, run_id, changes)
                await self._record_plan(db, run_id, changes)
            await run_events_repo.add_event(db, run_id, "node_finished", {"node": node})

    async def _record_options(self, db: aiosqlite.Connection, run_id: str, changes: dict) -> None:
        """Save what the options steps changed, and announce it, so the Options step fills in live."""
        if changes.get("options"):
            await options_repo.save_options(db, run_id, changes["options"])
            await run_events_repo.add_event(db, run_id, "options_updated", {
                "versions": len(changes["options"]), "presented": len(presented(changes["options"])),
            })
        fields: dict[str, Any] = {}
        if "selected_option_id" in changes:
            fields["selected"] = changes["selected_option_id"]
        if "no_recommendation" in changes:
            fields["no_recommendation"] = changes["no_recommendation"]
        if changes.get("options_notes"):
            fields["notes"] = list(changes["options_notes"])
        if fields:
            await options_repo.save_state(db, run_id, **fields)
            # The selection or the notes changed: tell the page, so it reloads the options (no new versions here).
            await run_events_repo.add_event(db, run_id, "options_updated", {"selected": changes.get("selected_option_id")})
        if changes.get("approved_option"):
            approved = changes["approved_option"]
            await run_events_repo.add_event(db, run_id, "option_approved", {"id": approved["id"], "version": approved["version"]})

    async def _record_plan(self, db: aiosqlite.Connection, run_id: str, changes: dict) -> None:
        """Save what the plan steps changed into the current plan, announce it, and complete the run once exported."""
        keys = ("roadmap", "plan_files", "plan_links", "plan_export", "plan_passed", "plan_outcome", "plan_notes")
        if not any(key in changes for key in keys):
            return
        if not await plans_repo.save_progress(db, run_id, changes):
            return
        await run_events_repo.add_event(db, run_id, "plan_updated", {"exported": bool(changes.get("plan_export"))})
        if changes.get("plan_export"):
            run = await runs_repo.get_run(db, run_id)
            if run.status == RunStatus.BUILDING_PLAN:
                outcome = (changes["plan_export"].get("outcome") or "full")
                await runs_repo.change_status(db, run_id, RunStatusChange(
                    status=RunStatus.COMPLETED, outcome=outcome,
                    outcome_note=None if outcome == "full" else "Some prompt checks still failed after the retry; see the plan notes.",
                ))

    async def _record_research(self, db: aiosqlite.Connection, run_id: str, node: str, changes: dict) -> None:
        """Save what an agent reported, and announce it, so the Research tab fills in live."""
        mode = self._settings.github_mode

        if changes.get("capabilities"):
            capabilities = [Capability.model_validate(c) for c in changes["capabilities"]]
            await research_repo.save_capabilities(db, run_id, capabilities, mode)
            await run_events_repo.add_event(db, run_id, "capabilities_recorded", {"count": len(capabilities)})
        if changes.get("components"):
            components = [ComponentCandidate.model_validate(c) for c in changes["components"]]
            await research_repo.save_components(db, run_id, components, mode)
            await run_events_repo.add_event(db, run_id, "components_proposed", {"count": len(components)})
        if changes.get("projects"):
            await research_repo.save_projects(db, run_id, [SimilarProject.model_validate(p) for p in changes["projects"]], mode)
        if changes.get("review"):
            await research_repo.save_review(db, run_id, ReviewVerdict.model_validate(changes["review"]), mode)
        for data in changes.get("repos") or []:
            await research_repo.save_repo(db, run_id, RepoEvidence.model_validate(data))
        if changes.get("evidence"):
            await research_repo.save_evidence(db, run_id, [EvidenceItem.model_validate(e) for e in changes["evidence"]])
        if changes.get("research_notes"):
            await research_repo.add_notes(db, run_id, list(changes["research_notes"]), mode)
        for data in changes.get("team_messages") or []:
            team_message = TeamMessage.model_validate(data)
            await research_repo.save_messages(db, run_id, [team_message], mode)
            await run_events_repo.add_event(db, run_id, "team_message", {
                "sender": team_message.sender, "recipient": team_message.recipient,
                "kind": team_message.kind, "message": team_message.content[:300],
            })
        if changes.get("research_finished"):
            await research_repo.mark_finished(db, run_id, mode)
        if changes.get("receipts"):
            await research_repo.save_receipts(db, run_id, changes["receipts"], mode)
        if changes.get("eligibility"):
            await research_repo.save_eligibility(db, run_id, changes["eligibility"], mode)
            counts: dict[str, int] = {}
            for item in changes["eligibility"]:
                counts[item["status"]] = counts.get(item["status"], 0) + 1
            await run_events_repo.add_event(db, run_id, "eligibility_decided", counts)

    # --- Forgetting a run -------------------------------------------------------
    async def forget_run(self, run_id: str) -> None:
        """Remove a run's saved checkpoints.

        LEARNING NOTE: two places hold a run's data. Archway's own tables are
        cleaned up by the database itself (ON DELETE CASCADE). LangGraph's
        checkpoints live in a separate file that knows nothing about our
        tables, so they must be removed here, by thread id.
        """
        await self._graph.checkpointer.adelete_thread(run_id)
        self._locks.pop(run_id, None)

    # --- A full picture of a run, for the UI -----------------------------------
    async def _asked_questions(self, run_id: str) -> list[AskedQuestion]:
        """The questions this run asked, each with the user's answer (None = skipped).

        Answers come from `answered_questions` in the saved state. Runs saved
        before that field existed only have the answers inside `user_texts`,
        written by the clarify node as "Answer about <topic>: <text>", so those
        are read back from there.
        """
        values = (await self._graph.aget_state(self._config(run_id))).values or {}
        answers = {item["topic"]: item["answer"] for item in values.get("answered_questions", [])}
        if not answers:
            for text in values.get("user_texts", []):
                prefix, sep, rest = text.partition(": ")
                if sep and prefix.startswith("Answer about "):
                    answers[prefix.removeprefix("Answer about ")] = rest
        return [
            AskedQuestion(topic=q["topic"], question=q["question"], answer=answers.get(q["topic"]))
            for q in values.get("asked_questions", [])
        ]

    async def snapshot(self, run_id: str) -> RunSnapshot:
        async with open_connection(self._settings.database_path) as db:
            run = await runs_repo.get_run(db, run_id)  # raises NotFound for an unknown id
            brief = await briefs_repo.latest_brief(db, run_id)
            versions = [item.version for item in await briefs_repo.list_briefs(db, run_id)]
            calls = await usage_repo.calls_by_service(db, run_id)
            last_event = await run_events_repo.last_event_id(db, run_id)

        waiting, _, finished = await self._waiting_for(run_id)
        asked = await self._asked_questions(run_id)
        # A run that is still being driven is never "finished": mid-step, the
        # checkpoint can briefly show no next node. It is finished once the
        # graph has ended AND the background work has let go of the run.
        running = self.is_running(run_id)
        finished = finished and not running
        # Just after a reply is sent, the saved state can still show the pause it answered while the run already works
        # on in the background (found live: a change request showed the old choice). Working is not waiting.
        if running:
            waiting = None
        usage = [
            UsageCount(service="llm", calls=calls.get("llm", 0), cap=self._settings.max_llm_calls_per_run),
            UsageCount(service="jev", calls=calls.get("jev", 0), cap=self._settings.max_jev_calls_per_run),
            UsageCount(service="github", calls=calls.get("github", 0), cap=None),
        ]
        return RunSnapshot(
            run=run, waiting_for=waiting, finished=finished, running=running, brief=brief,
            brief_versions=versions, usage=usage, last_event_id=last_event, asked_questions=asked,
        )
