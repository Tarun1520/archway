"""
Tests for the run lifecycle rules in app/models/lifecycle.py.

These are pure-Python tests: no database, no web server. That is the benefit
of keeping the rules in one plain function.
"""

import pytest

from app.models.lifecycle import InvalidTransition, RunStatus, check_transition

S = RunStatus  # a short alias to keep the tests readable


def test_the_normal_forward_path_is_allowed():
    check_transition(S.DRAFT, S.RESEARCHING, brief_confirmed=True)
    check_transition(S.RESEARCHING, S.AWAITING_SELECTION, brief_confirmed=True)
    check_transition(S.AWAITING_SELECTION, S.BUILDING_PLAN, brief_confirmed=True)
    check_transition(S.BUILDING_PLAN, S.COMPLETED, brief_confirmed=True, outcome="full")


def test_research_cannot_start_before_the_brief_is_confirmed():
    with pytest.raises(InvalidTransition, match="before the brief is confirmed"):
        check_transition(S.DRAFT, S.RESEARCHING, brief_confirmed=False)


def test_steps_cannot_be_skipped():
    with pytest.raises(InvalidTransition):
        check_transition(S.DRAFT, S.AWAITING_SELECTION, brief_confirmed=True)
    with pytest.raises(InvalidTransition):
        check_transition(S.RESEARCHING, S.BUILDING_PLAN, brief_confirmed=True)


def test_going_backwards_is_not_allowed():
    with pytest.raises(InvalidTransition):
        check_transition(S.AWAITING_SELECTION, S.RESEARCHING, brief_confirmed=True)


@pytest.mark.parametrize("working", [S.DRAFT, S.RESEARCHING, S.AWAITING_SELECTION, S.BUILDING_PLAN])
@pytest.mark.parametrize("stop", [S.FAILED, S.PAUSED, S.CANCELLED])
def test_any_working_state_can_fail_pause_or_cancel(working, stop):
    check_transition(working, stop, brief_confirmed=False)


@pytest.mark.parametrize("terminal", [S.COMPLETED, S.FAILED, S.CANCELLED])
def test_terminal_states_cannot_change(terminal):
    for target in RunStatus:
        with pytest.raises(InvalidTransition):
            check_transition(terminal, target, brief_confirmed=True, outcome="full")


def test_a_paused_run_resumes_only_to_where_it_was():
    check_transition(S.PAUSED, S.RESEARCHING, brief_confirmed=True, paused_from=S.RESEARCHING)
    with pytest.raises(InvalidTransition):
        check_transition(S.PAUSED, S.BUILDING_PLAN, brief_confirmed=True, paused_from=S.RESEARCHING)
    # It may still be cancelled or fail while paused.
    check_transition(S.PAUSED, S.CANCELLED, brief_confirmed=True, paused_from=S.RESEARCHING)


def test_completing_requires_an_outcome():
    with pytest.raises(InvalidTransition, match="outcome"):
        check_transition(S.BUILDING_PLAN, S.COMPLETED, brief_confirmed=True)


def test_an_early_finish_is_completed_with_partial_or_abstained_never_full():
    """Abstention is a valid COMPLETED result, not a failure."""
    check_transition(S.RESEARCHING, S.COMPLETED, brief_confirmed=True, outcome="abstained")
    check_transition(S.AWAITING_SELECTION, S.COMPLETED, brief_confirmed=True, outcome="partial")
    with pytest.raises(InvalidTransition):
        check_transition(S.RESEARCHING, S.COMPLETED, brief_confirmed=True, outcome="full")
    with pytest.raises(InvalidTransition):  # nothing has happened yet in draft
        check_transition(S.DRAFT, S.COMPLETED, brief_confirmed=True, outcome="abstained")
