"""
Run lifecycle: which state a run is in, and which moves are allowed.

    draft -> researching -> awaiting_selection -> building_plan -> completed

What this file does
    Defines the states and ONE function, `check_transition`, that says
    whether a move from one state to another is allowed. It is pure Python
    with no database and no web code, so it is easy to test.

The rules (IMPLEMENTATION_GUIDE.md section 4.1)
    - A run cannot leave `draft` without a confirmed brief.
    - Any non-terminal state may go to `failed`, `paused` or `cancelled`.
    - `paused` resumes ONLY to the state it was paused from.
    - `completed`, `failed`, `cancelled` are terminal: nothing follows them.
    - A run that ends early with a partial result or an abstention is
      `completed` with an outcome that says so. It is not `failed`.

How it plugs in
    app/db/runs_repo.py calls `check_transition` before saving a new status.
"""

from enum import StrEnum
from typing import Literal


class RunStatus(StrEnum):
    """LEARNING NOTE: StrEnum
    An enum is a fixed list of named values. A StrEnum's values are also
    plain text, so they store in the database and travel as JSON unchanged.
    """

    DRAFT = "draft"
    RESEARCHING = "researching"
    AWAITING_SELECTION = "awaiting_selection"
    BUILDING_PLAN = "building_plan"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
    CANCELLED = "cancelled"


# How a finished run ended. None while the run is still going.
RunOutcome = Literal["full", "partial", "abstained"]

TERMINAL_STATES = {RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED}

# The normal forward path: each state and the ONE state that follows it.
NEXT_STEP = {
    RunStatus.DRAFT: RunStatus.RESEARCHING,
    RunStatus.RESEARCHING: RunStatus.AWAITING_SELECTION,
    RunStatus.AWAITING_SELECTION: RunStatus.BUILDING_PLAN,
    RunStatus.BUILDING_PLAN: RunStatus.COMPLETED,
}

# States from which a run may finish EARLY (partial result or abstention).
CAN_FINISH_EARLY = {RunStatus.RESEARCHING, RunStatus.AWAITING_SELECTION}


class InvalidTransition(ValueError):
    """Raised when a status change breaks the lifecycle rules."""


def check_transition(
    current: RunStatus,
    target: RunStatus,
    *,
    brief_confirmed: bool,
    paused_from: RunStatus | None = None,
    outcome: RunOutcome | None = None,
) -> None:
    """Return quietly if the move is allowed, otherwise raise InvalidTransition.

    LEARNING NOTE: the `*` in the argument list
      Everything after `*` must be passed by name, e.g. brief_confirmed=True.
      That makes calls readable and prevents mixing up the arguments.
    """
    if current in TERMINAL_STATES:
        raise InvalidTransition(f"a run that is {current.value} cannot change state")

    if target == current:
        raise InvalidTransition(f"the run is already {current.value}")

    # --- Leaving a pause ------------------------------------------------------
    if current == RunStatus.PAUSED:
        if target in (RunStatus.FAILED, RunStatus.CANCELLED):
            return
        if target == paused_from:
            return
        raise InvalidTransition(
            f"a paused run can only resume to {paused_from.value if paused_from else 'its previous state'}"
        )

    # --- Stopping from any working state --------------------------------------
    if target in (RunStatus.FAILED, RunStatus.PAUSED, RunStatus.CANCELLED):
        return

    # --- Finishing ------------------------------------------------------------
    if target == RunStatus.COMPLETED:
        if outcome is None:
            raise InvalidTransition("a completed run must record its outcome (full, partial or abstained)")
        if current == RunStatus.BUILDING_PLAN:
            return
        if current in CAN_FINISH_EARLY:
            if outcome == "full":
                raise InvalidTransition(
                    f"a run finishing early from {current.value} must be 'partial' or 'abstained', not 'full'"
                )
            return
        raise InvalidTransition(f"a run cannot complete from {current.value}")

    # --- The normal forward step ---------------------------------------------
    if NEXT_STEP.get(current) != target:
        raise InvalidTransition(f"{current.value} -> {target.value} is not an allowed step")

    if current == RunStatus.DRAFT and not brief_confirmed:
        raise InvalidTransition("research cannot start before the brief is confirmed")
