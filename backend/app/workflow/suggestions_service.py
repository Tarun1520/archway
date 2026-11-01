"""
SuggestionService: asks the model for ideas to complete a brief.

What this file does
    For the newest, unconfirmed brief of a run:
      1. returns saved suggestions if this version already has them;
      2. otherwise checks the run's model-call cap, asks the model once,
         counts the call, cleans the reply with plain Python, saves it, and
         returns it.

Why it is not a graph node
    Suggestions are help for a person who is editing a draft. They are not a
    step the workflow must pass through, and the run is paused (waiting for
    the user) while they are made. A separate service keeps the workflow
    graph exactly as drawn.

The cap
    Calls are counted in the usage table, which is the true total for the
    run. Reaching the cap refuses with a clear message instead of spending.

How it plugs in
    app/main.py creates one at start-up; app/api/suggestions.py calls it.
"""

import asyncio

import aiosqlite
from pydantic import ValidationError

from app.briefing.suggestion_prompt import SUGGEST_SYSTEM_PROMPT, suggestion_user_prompt
from app.briefing.suggestions import MAX_UNKNOWNS, clean_suggestions, standard_answers
from app.config.settings import Settings
from app.db import briefs_repo, runs_repo, suggestions_repo, usage_repo
from app.llm.base import LLMClient, LLMError
from app.models.common import utc_now
from app.models.suggestions import SUGGESTIONS_SCHEMA, BriefSuggestions, SuggestionsDraft
from app.models.usage import UsageEvent
from app.workflow.service import WorkflowConflict


# How many open questions the first call covers, and how many each follow-up
# covers. Small batches keep each reply short enough for the model to finish.
FIRST_BATCH = 3
FOLLOW_UP_BATCH = 4
MAX_FOLLOW_UPS = 2


def _missing(brief, suggestions: BriefSuggestions) -> list[str]:
    """The brief's open questions that have no answers yet."""
    have = {group.unknown for group in suggestions.unknowns}
    return [text for text in brief.unknowns[:MAX_UNKNOWNS] if text not in have]


class SuggestionService:
    def __init__(self, *, settings: Settings, llm: LLMClient):
        self._settings = settings
        self._llm = llm
        # One lock per (run, version): two requests for the same suggestions
        # (for example a page loading twice) make ONE model call.
        self._locks: dict[tuple[str, int], asyncio.Lock] = {}

    async def suggestions_for(
        self, db: aiosqlite.Connection, run_id: str, *, retry_standard: bool = False
    ) -> BriefSuggestions:
        await runs_repo.get_run(db, run_id)  # raises NotFound for an unknown run
        brief = await briefs_repo.latest_brief(db, run_id)
        if brief is None:
            raise WorkflowConflict("there is no brief to make suggestions for yet")
        if brief.confirmed:
            raise WorkflowConflict("this brief is already confirmed; suggestions are only made for a draft")

        lock = self._locks.setdefault((run_id, brief.version), asyncio.Lock())
        async with lock:
            saved = await suggestions_repo.get_suggestions(db, run_id, brief.version)
            if saved is not None and saved.schema_version < SUGGESTIONS_SCHEMA:
                saved = None  # written before newer blocks existed: write them again
            if saved is not None and retry_standard:
                # The person asked the AI to try again for questions that only
                # have generic options: forget those groups and ask for them.
                kept = [group for group in saved.unknowns if not all(a.standard for a in group.answers)]
                saved = saved.model_copy(update={"unknowns": kept})
            if saved is not None and not _missing(brief, saved):
                return saved

            cap = self._settings.max_llm_calls_per_run
            used = (await usage_repo.calls_by_service(db, run_id)).get("llm", 0)

            if saved is None:
                if used >= cap:
                    raise WorkflowConflict(
                        f"this run has used its {cap} model calls, so no suggestions were generated; "
                        "you can still edit the brief yourself"
                    )
                # The first call covers every block, and only the first few open
                # questions, so the reply stays short enough to finish.
                first = brief.model_copy(update={"unknowns": brief.unknowns[:FIRST_BATCH]})
                draft, model = await self._ask(db, run_id, first)
                used += 1
                cleaned = clean_suggestions(draft, first, mode=self._llm.mode, model=model)
            else:
                cleaned = saved  # an earlier save that is still missing some questions

            # Ask again, for the questions still without answers, a limited
            # number of times. A failed follow-up is not fatal.
            for _ in range(MAX_FOLLOW_UPS):
                missing = _missing(brief, cleaned)
                if not missing or used >= cap:
                    break
                batch = brief.model_copy(update={"unknowns": missing[:FOLLOW_UP_BATCH]})
                try:
                    extra_draft, _ = await self._ask(db, run_id, batch)
                except LLMError:
                    break
                used += 1
                extra = clean_suggestions(extra_draft, batch, mode=self._llm.mode, model=cleaned.model)
                cleaned = cleaned.model_copy(update={"unknowns": cleaned.unknowns + extra.unknowns})

            # No open question is left without something to choose from.
            for question in _missing(brief, cleaned):
                cleaned = cleaned.model_copy(update={"unknowns": cleaned.unknowns + [standard_answers(question)]})

            await suggestions_repo.save_suggestions(db, run_id, cleaned)
            return cleaned

    async def _ask(self, db: aiosqlite.Connection, run_id: str, brief) -> tuple[SuggestionsDraft, str | None]:
        """One model call: counted as soon as it happens, then checked against the strict shape."""
        result = await self._llm.complete_json(
            step="suggest",
            system=SUGGEST_SYSTEM_PROMPT,
            user=suggestion_user_prompt(brief),
            schema_name="brief_suggestions",
            schema=SuggestionsDraft.model_json_schema(),
        )
        tokens = None
        if result.input_tokens is not None and result.output_tokens is not None:
            tokens = result.input_tokens + result.output_tokens
        await usage_repo.add_usage(db, UsageEvent(
            run_id=run_id, service="llm", mode=self._llm.mode, count=1,
            tokens_if_known=tokens, timestamp=utc_now(),
        ))
        try:
            return SuggestionsDraft.model_validate(result.data), result.model
        except ValidationError as error:
            raise LLMError(
                f"the model's suggestions did not match the expected shape ({error.error_count()} problems)"
            ) from error
