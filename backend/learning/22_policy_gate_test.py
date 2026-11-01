"""
Tests for Lesson 22 (and a graph test for Lesson 03).

How to run (from the project root)
    backend/.venv/bin/python -m pytest backend/learning/22_policy_gate_test.py -q

LEARNING NOTE: what is a test?
    A test is a function whose name starts with `test_`. pytest finds them,
    runs each one, and reports pass or fail. `assert x == y` fails the test
    if the two sides differ. Good tests check the RULES, not the details.

LEARNING NOTE: why importlib?
    The lesson files start with a digit (22_policy_gate.py), which normal
    `import` statements cannot name. importlib can load a file by its path.
"""

import importlib.util
import random
from pathlib import Path

HERE = Path(__file__).parent


def load(filename: str):
    spec = importlib.util.spec_from_file_location(filename.removesuffix(".py"), HERE / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gate = load("22_policy_gate.py")
loop = load("03_routing_and_loops.py")


# -----------------------------------------------------------------------------
# Policy tests
# -----------------------------------------------------------------------------
def test_missing_license_needs_review_not_eligible():
    repo = gate.Repo("x", license=None, archived=False, suitability=0.9, supports_required_feature=True)
    assert gate.check_eligibility(repo).status == "review_required"


def test_excluded_license_is_excluded_even_with_perfect_score():
    repo = gate.Repo("x", license="GPL-3.0", archived=False, suitability=1.0, supports_required_feature=True)
    assert gate.check_eligibility(repo).status == "excluded"


def test_unknown_stays_unknown_not_assumed_fine():
    # archived=None means "not retrieved". It must not be treated as False.
    repo = gate.Repo("x", license="MIT", archived=None, suitability=0.5, supports_required_feature=None)
    assert gate.check_eligibility(repo).status == "unresolved"


def test_ineligible_repo_never_ranks_above_an_eligible_one():
    """The invariant, checked on many random inputs rather than one example."""
    generator = random.Random(1234)  # fixed seed: same "random" data every run
    licenses = ["MIT", "Apache-2.0", "GPL-3.0", None]
    for _ in range(200):
        repos = [
            gate.Repo(
                name=f"r{n}",
                license=generator.choice(licenses),
                archived=generator.choice([True, False, None]),
                suitability=generator.random(),
                supports_required_feature=generator.choice([True, False, None]),
            )
            for n in range(generator.randint(1, 8))
        ]
        ranked = gate.rank(repos)
        statuses = [result.status for _, result in ranked]
        if "eligible" in statuses:
            assert statuses[0] == "eligible", statuses


# -----------------------------------------------------------------------------
# A graph test (Lesson 03's graph)
# -----------------------------------------------------------------------------
def run_loop_graph(evidence_per_round: int) -> str:
    start = {
        "evidence_per_round": evidence_per_round,
        "evidence_count": 0,
        "research_rounds": 0,
        "outcome": "",
    }
    return loop.build_graph().invoke(start)["outcome"]


def test_graph_drafts_options_when_evidence_is_enough():
    assert run_loop_graph(6).startswith("options drafted")


def test_graph_abstains_at_the_round_limit():
    assert run_loop_graph(1).startswith("abstained")


def test_graph_never_exceeds_the_round_limit():
    start = {"evidence_per_round": 0, "evidence_count": 0, "research_rounds": 0, "outcome": ""}
    final = loop.build_graph().invoke(start)
    assert final["research_rounds"] == loop.MAX_RESEARCH_ROUNDS
