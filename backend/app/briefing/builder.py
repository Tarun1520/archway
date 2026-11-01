"""
Building a ProjectBrief: the step between "what the model said" and "what
Archway stores".

What this file does
    Four small functions, each returning a NEW brief (nothing is changed in
    place, so every earlier version stays intact):

      build_brief       model draft        -> brief version N
      add_assumptions   skipped questions  -> brief version N+1
      apply_edit        the user's edit    -> brief version N+1
      mark_confirmed    the user approved  -> same version, confirmed=True

Why this is plain Python and not left to the model
    These are the promises of Checkpoint 2, and each is kept by code here:
      - Stated constraints are never silently dropped
          (find_stated_constraints + the "keep the earlier value" merge)
      - Assumptions stay separate from what the user said
          (they only ever go into `assumptions`)
      - Conflicting requirements are flagged
          (find_conflicts runs on every build and every edit)
      - Requirement ids are stable
          (an item whose text is unchanged keeps its id across versions)

How it plugs in
    Called by the graph nodes in app/graph/nodes/.
"""

from app.briefing.similarity import is_similar
from app.models.brief import Assumption, Conflict, Constraints, ProjectBrief, Requirement
from app.models.brief_draft import BriefDraft
from app.models.workflow import BriefEdit, EditedItem
from app.policy.clarification import ASSUMPTION_IF_SKIPPED, SKIPPED_REASON
from app.policy.grounding import ground_stack, requirements_naming, restates_assumption

NOT_NAMED_REASON = "You did not name this tool; Archway suggested it. Keep it, change it or remove it before approving."
from app.policy.conflicts import RULES, find_conflicts
from app.policy.stated_constraints import find_stated_constraints

_RULE_EXPLANATIONS = {rule.explanation for rule in RULES}


def _normalise(text: str) -> str:
    """Lower-case and squeeze spaces, so "Works  Offline" equals "works offline"."""
    return " ".join(text.lower().split())


def _next_number(existing_ids: list[str], prefix: str) -> int:
    """The next free number for ids like REQ-1, REQ-2 ... (never reuses a number)."""
    numbers = [int(item[len(prefix):]) for item in existing_ids
               if item.startswith(prefix) and item[len(prefix):].isdigit()]
    return max(numbers, default=0) + 1


def _requirements_from_texts(texts: list[str], previous: list[Requirement], prefix: str) -> list[Requirement]:
    """Give each text an id, reusing the earlier id when the text is unchanged.

    LEARNING NOTE: why stable ids matter
      Evidence and decisions will later point at "REQ-2". If re-reading the
      idea renumbered everything, those links would silently point at the
      wrong requirement.

    New items get the LOWEST free number. This function only runs while the
    model is (re)drafting, before the brief is confirmed, so nothing points
    at a requirement yet and an id that dropped out can safely be reused.
    (Without this, a second draft that reworded every item started at REQ-6.)
    After confirmation, changes go through `apply_edit`, which never reuses.
    """
    by_text = {_normalise(item.text): item.id for item in previous}

    # First pass: unchanged texts keep their old id.
    rows, seen = [], set()
    for text in texts:
        text = text.strip()
        key = _normalise(text)
        if not text or key in seen:
            continue  # skip blanks and exact repeats
        seen.add(key)
        rows.append((by_text.get(key), text))

    # Second pass: new texts take the lowest numbers not already kept.
    taken = {item_id for item_id, _ in rows if item_id}
    number = 1
    result = []
    for item_id, text in rows:
        if item_id is None:
            while f"{prefix}{number}" in taken:
                number += 1
            item_id = f"{prefix}{number}"
            taken.add(item_id)
        result.append(Requirement(id=item_id, text=text))
    return result


def _topic_assumptions(topics: list[str]) -> list[Assumption]:
    """One visible assumption per question the user chose to skip."""
    return [
        Assumption(id=f"ASM-{topic}", text=ASSUMPTION_IF_SKIPPED[topic], reason=SKIPPED_REASON)
        for topic in topics
    ]


def _model_conflicts(draft: BriefDraft, requirements: list[Requirement]) -> list[Conflict]:
    """Conflicts the MODEL suggested, with requirement texts turned into ids."""
    ids_by_text = {_normalise(item.text): item.id for item in requirements}
    conflicts = []
    for item in draft.conflicts:
        ids = [ids_by_text[_normalise(text)] for text in item.requirement_texts if _normalise(text) in ids_by_text]
        conflicts.append(Conflict(description=item.description, requirement_ids=ids))
    return conflicts


def _merge_conflicts(*groups: list[Conflict]) -> list[Conflict]:
    """Join conflict lists without showing the same clash twice.

    The rule-based conflicts come first. A later conflict (for example one the
    model suggested) that involves any of the same requirements is treated as
    the same clash said in other words: its requirement ids are added to the
    earlier conflict instead of listing it again. Exact repeats are dropped.
    """
    merged: list[Conflict] = []
    for group in groups:
        for conflict in group:
            if any(conflict.description == existing.description for existing in merged):
                continue
            overlap = next((existing for existing in merged
                            if set(existing.requirement_ids) & set(conflict.requirement_ids)), None)
            if overlap is not None:
                extra = [item for item in conflict.requirement_ids if item not in overlap.requirement_ids]
                merged[merged.index(overlap)] = overlap.model_copy(
                    update={"requirement_ids": overlap.requirement_ids + extra})
                continue
            merged.append(conflict)
    return merged


def build_brief(
    *,
    run_id: str,
    draft: BriefDraft,
    previous: ProjectBrief | None,
    user_texts: list[str],
    assumed_topics: list[str],
) -> ProjectBrief:
    """Turn a model draft into the next brief version."""
    # Integrations the user said are mandatory become must-have requirements.
    # (Skipped when a must-have already says the same thing: a live run showed
    # "The app must integrate a payment gateway" AND "Integrate with payment
    # gateway" as two requirements.)
    must_texts = list(draft.must_have)
    for name in draft.mandatory_integrations or []:
        text = f"Integrate with {name}"
        if not any(is_similar(text, existing) for existing in must_texts):
            must_texts.append(text)

    must_have = _requirements_from_texts(must_texts, previous.must_have if previous else [], "REQ-")
    nice_to_have = _requirements_from_texts(draft.nice_to_have, previous.nice_to_have if previous else [], "NICE-")

    # NEVER DROP: if the model returns null for a constraint that an earlier
    # version had, keep the earlier value. The user's own sentences are found
    # again from the text every time, plus anything kept from before.
    earlier = previous.constraints if previous else Constraints()
    stated = list(earlier.stated)
    for sentence in find_stated_constraints(user_texts):
        if sentence not in stated:
            stated.append(sentence)
    constraints = Constraints(
        budget=draft.budget or earlier.budget,
        privacy=draft.privacy or earlier.privacy,
        deployment=draft.deployment or earlier.deployment,
        stated=stated,
    )

    # Tools the person did not name are the model's guesses: they move to the assumptions (shown as assumed),
    # and so does any must-have that names one of them (app/policy/grounding.py).
    stack, not_named = ground_stack([item.strip() for item in draft.stack_preferences if item.strip()], user_texts)
    moved = set(requirements_naming([r.text for r in must_have], not_named, user_texts))
    # And any requirement that only repeats one of the model's own assumptions (app/policy/grounding.py).
    guesses = [item.text for item in draft.assumptions if item.text.strip()]
    moved |= {r.text for r in must_have + nice_to_have if restates_assumption(r.text, guesses, user_texts)}
    must_have = [r for r in must_have if r.text not in moved]
    nice_to_have = [r for r in nice_to_have if r.text not in moved]

    assumptions = [
        Assumption(id=f"ASM-{number}", text=item.text, reason=item.reason)
        for number, item in enumerate(draft.assumptions, start=1)
        if item.text.strip()
    ] + [
        Assumption(id=f"ASM-tool-{number}", text=f"Assumed tool: {entry}", reason=NOT_NAMED_REASON)
        for number, entry in enumerate(not_named, start=1)
    ] + [
        Assumption(id=f"ASM-req-{number}", text=f"Assumed requirement: {text}", reason=NOT_NAMED_REASON)
        for number, text in enumerate(sorted(moved), start=1)
    ] + _topic_assumptions(assumed_topics)

    conflicts = _merge_conflicts(find_conflicts(constraints, must_have + nice_to_have),
                                 _model_conflicts(draft, must_have + nice_to_have))

    return ProjectBrief(
        id=f"brief-{run_id}",
        version=(previous.version + 1) if previous else 1,
        problem=(draft.problem or "").strip() or (previous.problem if previous else "Not stated"),
        users=draft.users or (previous.users if previous else None),
        must_have=must_have,
        nice_to_have=nice_to_have,
        stack_preferences=stack,
        constraints=constraints,
        assumptions=assumptions,
        unknowns=[item.strip() for item in draft.unknowns if item.strip()],
        conflicts=conflicts,
        confirmed=False,
    )


def add_assumptions(previous: ProjectBrief, topics: list[str]) -> ProjectBrief:
    """A new version in which each skipped question became a visible assumption."""
    existing_ids = {item.id for item in previous.assumptions}
    added = [item for item in _topic_assumptions(topics) if item.id not in existing_ids]
    return previous.model_copy(
        update={"version": previous.version + 1, "assumptions": previous.assumptions + added, "confirmed": False}
    )


def _items_with_ids(edited: list[EditedItem], previous_ids: list[str], prefix: str) -> list[tuple[str, str]]:
    """(id, text) pairs for edited items: keep a given id, create one otherwise."""
    used = list(previous_ids)
    result = []
    for item in edited:
        item_id = item.id if item.id else f"{prefix}{_next_number(used, prefix)}"
        if item_id in [existing for existing, _ in result]:
            raise ValueError(f"the id {item_id} is used twice in the edit")
        used.append(item_id)
        result.append((item_id, item.text.strip()))
    return result


def apply_edit(previous: ProjectBrief, edit: BriefEdit) -> ProjectBrief:
    """The user's edit as a new, unconfirmed version, with conflicts re-checked.

    An edit is the user's own decision, so removing a stated constraint here
    is allowed: it is not "silent", the user did it on purpose.
    """
    must_have = [Requirement(id=item_id, text=text)
                 for item_id, text in _items_with_ids(edit.must_have, [r.id for r in previous.must_have], "REQ-")]
    nice_to_have = [Requirement(id=item_id, text=text)
                    for item_id, text in _items_with_ids(edit.nice_to_have, [r.id for r in previous.nice_to_have], "NICE-")]
    assumptions = [
        Assumption(id=item_id, text=text,
                   reason=next((a.reason for a in previous.assumptions if a.id == item_id), None))
        for item_id, text in _items_with_ids(edit.assumptions, [a.id for a in previous.assumptions], "ASM-")
    ]

    # Keep model-suggested conflicts whose requirements still exist; re-run the rules.
    remaining_ids = {item.id for item in must_have + nice_to_have}
    kept = [conflict for conflict in previous.conflicts
            if conflict.description not in _RULE_EXPLANATIONS
            and all(item in remaining_ids for item in conflict.requirement_ids)]
    conflicts = _merge_conflicts(find_conflicts(edit.constraints, must_have + nice_to_have), kept)

    return ProjectBrief(
        id=previous.id,
        version=previous.version + 1,
        problem=edit.problem.strip(),
        users=(edit.users or "").strip() or None,
        must_have=must_have,
        nice_to_have=nice_to_have,
        stack_preferences=[item.strip() for item in edit.stack_preferences if item.strip()],
        constraints=edit.constraints,
        assumptions=assumptions,
        unknowns=[item.strip() for item in edit.unknowns if item.strip()],
        conflicts=conflicts,
        confirmed=False,
    )


def mark_confirmed(brief: ProjectBrief) -> ProjectBrief:
    """The same version, now approved by the user."""
    return brief.model_copy(update={"confirmed": True})
