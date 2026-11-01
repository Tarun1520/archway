"""
The whole pipeline on every sample brief, offline (Checkpoint 6, run in CI with no paid calls).

Each sample brief goes from idea to exported plan in fixture mode. This checks the promises that must hold
whatever a model would say: no part that is not eligible is ever reused, a planted instruction in a README is
never followed, every exported plan passes the prompt rubric, and every scenario the samples were written for
really happens (except the one only a real model can show). Two run conditions are checked too.
"""

from evaluation.pipeline import run_all


def test_every_sample_brief_through_the_whole_pipeline():
    results = run_all(fixture=True)
    for run in results["runs"]:
        assert run["eligibility_errors"] == 0, run["slug"]
        assert not run["injection_followed"], run["slug"]
        assert run["scenario_seen"] is not False, f"{run['slug']}: its scenario did not happen"
        if run["plan_outcome"]:
            assert run["prompts"] and run["prompts_passed"] == run["prompts"], run["slug"]
            assert run["requirement_coverage"] == 1.0, run["slug"]
        else:
            assert run["abstained"], f"{run['slug']}: no plan and no honest abstention ({run['stopped']})"

    unavailable, capped = results["conditions"]
    assert unavailable["decision_notes"] and unavailable["plan_outcome"]  # rules alone, said so, and still a plan
    assert any("cap" in (error or "") for error in capped["errors"])  # stopped and said why
