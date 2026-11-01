"""
Cleaning the model's suggestions with plain Python.

What this file does
    Takes what the model returned (SuggestionsDraft) and the brief it was
    written for, and returns the suggestions the UI may show.

The rules (the model proposes, code decides)
    - At most MAX_PER_BLOCK suggestions in each block, and at most
      MAX_PER_BLOCK answers for each unknown.
    - Blank or very long text is dropped.
    - A suggestion that repeats something already in the brief (or an earlier
      suggestion) is dropped.
    - A constraint suggestion may only fill a field that is still empty.
    - Answers are kept only for unknowns that really exist in the brief; the
      model cannot invent a question.

How it plugs in
    app/workflow/suggestions_service.py calls `clean_suggestions`.
"""

import re

from app.briefing.similarity import is_similar
from app.models.brief import ProjectBrief
from app.models.common import ServiceMode
from app.models.suggestions import (
    AnswerSuggestion,
    BriefSuggestions,
    ConstraintSuggestion,
    Suggestion,
    SUGGESTIONS_SCHEMA,
    SuggestionsDraft,
    UnknownAnswers,
)

MAX_PER_BLOCK = 5
MAX_TEXT_LENGTH = 200
MAX_UNKNOWNS = 10  # how many of the brief's unknowns get suggested answers


def _tidy(text: str) -> str:
    return " ".join(text.split())


def _reason(text: str) -> str | None:
    cleaned = _tidy(text)
    return cleaned[:MAX_TEXT_LENGTH] if cleaned else None


def _usable(text: str, already: list[str]) -> str | None:
    """The tidied text, or None if it is empty, too long, or a repeat."""
    cleaned = _tidy(text)
    if not cleaned or len(cleaned) > MAX_TEXT_LENGTH:
        return None
    if any(is_similar(cleaned, other) for other in already):
        return None
    return cleaned


_FIGURE = re.compile(r"\d+(?:[.,]\d+)*")


def _invents_a_figure(text: str, brief: ProjectBrief) -> bool:
    """True when a constraint contains a number the person never gave.

    A constraint is something the person will adopt as their own limit. A
    model that writes "stay under $50 a month" has made up a budget. Numbers
    the brief already contains are fine.
    """
    figures = _FIGURE.findall(text)
    if not figures:
        return False
    known = " ".join([brief.problem, brief.users or "", *[item.text for item in brief.must_have + brief.nice_to_have],
                      *brief.constraints.stated, *brief.unknowns])
    return any(figure not in known for figure in figures)


def standard_answers(unknown: str) -> UnknownAnswers:
    """Generic options for a question the model gave no answer for.

    Every open question must have something to choose from. These are fixed
    wordings, written by code, and are marked `standard` so the UI says so.
    """
    note = "Standard option. The AI returned no answer for this question."
    return UnknownAnswers(unknown=unknown, answers=[
        AnswerSuggestion(text=f"Settle this before building starts: {unknown}", reason=note, add_as="must_have", standard=True),
        AnswerSuggestion(text=f"Use the simplest approach that works for now: {unknown}", reason=note, add_as="assumption", standard=True),
        AnswerSuggestion(text=f"Leave this for after the first version works: {unknown}", reason=note, add_as="assumption", standard=True),
    ])


def clean_suggestions(
    draft: SuggestionsDraft, brief: ProjectBrief, *, mode: ServiceMode, model: str | None
) -> BriefSuggestions:
    # Everything the brief already says, so nothing is suggested twice.
    in_brief = (
        [item.text for item in brief.must_have]
        + [item.text for item in brief.nice_to_have]
        + [item.text for item in brief.assumptions]
        + list(brief.constraints.stated)
        + list(brief.stack_preferences)
        + [value for value in (brief.constraints.budget, brief.constraints.privacy, brief.constraints.deployment) if value]
    )

    seen = list(in_brief)

    def take(items, build, limit=MAX_PER_BLOCK):
        kept = []
        for item in items:
            text = _usable(item.text, seen)
            if text is None:
                continue
            seen.append(text)
            kept.append(build(text, item))
            if len(kept) == limit:
                break
        return kept

    must_have = take(draft.must_have, lambda text, item: Suggestion(text=text, reason=_reason(item.reason)))
    assumptions = take(draft.assumptions, lambda text, item: Suggestion(text=text, reason=_reason(item.reason)))
    nice_to_have = take(draft.nice_to_have, lambda text, item: Suggestion(text=text, reason=_reason(item.reason)))
    stack = take(draft.stack, lambda text, item: Suggestion(text=text, reason=_reason(item.reason)))

    # A field can be filled only once, and only if it is still empty.
    empty_fields = {
        "budget": brief.constraints.budget is None,
        "privacy": brief.constraints.privacy is None,
        "deployment": brief.constraints.deployment is None,
        "stated": True,
    }
    constraints: list[ConstraintSuggestion] = []
    for item in draft.constraints:
        if len(constraints) == MAX_PER_BLOCK:
            break
        if not empty_fields[item.field]:
            continue
        text = _usable(item.text, seen)
        if text is None or _invents_a_figure(text, brief):
            continue
        seen.append(text)
        if item.field != "stated":
            empty_fields[item.field] = False
        constraints.append(ConstraintSuggestion(field=item.field, text=text, reason=_reason(item.reason)))

    # Answers: only for unknowns the brief really has.
    real_unknowns = {" ".join(text.split()).lower(): text for text in brief.unknowns[:MAX_UNKNOWNS]}
    unknowns: list[UnknownAnswers] = []
    for group in draft.unknowns:
        original = real_unknowns.get(" ".join(group.unknown.split()).lower())
        if original is None or any(existing.unknown == original for existing in unknowns):
            continue
        answers: list[AnswerSuggestion] = []
        used_here: list[str] = list(in_brief)
        for answer in group.answers:
            text = _usable(answer.text, used_here)
            if text is None:
                continue
            used_here.append(text)
            answers.append(AnswerSuggestion(text=text, reason=_reason(answer.reason), add_as=answer.add_as))
            if len(answers) == MAX_PER_BLOCK:
                break
        if answers:
            unknowns.append(UnknownAnswers(unknown=original, answers=answers))

    return BriefSuggestions(
        brief_version=brief.version, schema_version=SUGGESTIONS_SCHEMA, must_have=must_have,
        nice_to_have=nice_to_have, stack=stack, constraints=constraints,
        assumptions=assumptions, unknowns=unknowns, mode=mode, model=model,
    )
