"""The research evaluation: scoring rules, and the harness running offline."""

from evaluation.scoring import score_run, summary_table

CASE = {"id": "c", "must_find": [{"what": "tts", "any_of": ["piper", "kokoro"]}, {"what": "stt", "any_of": ["whisper"]}],
        "must_not": ["badlib"]}


def comp(name, fit, ref=None):
    return {"name": name, "fit": fit, "facts": {"reference": ref or name, "url": ""}}


def test_a_reference_only_component_does_not_satisfy_a_must_find():
    research = {"components": [comp("piper", 3), comp("whisper-demo-app", 1)], "projects": []}
    result = score_run(CASE, research, llm_calls=40, minutes=3, finished=True)
    assert [f["what"] for f in result["found"]] == ["tts"] and result["parts"]["coverage"] == 5.0


def test_precision_counts_judged_fit_and_must_not_hits():
    research = {"components": [comp("piper", 3), comp("x", 1), comp("badlib", 3), comp("y", 2)], "projects": []}
    result = score_run(CASE, research, llm_calls=40, minutes=3, finished=True)
    assert result["parts"]["precision"] == 5.0 and result["must_not_hits"] == ["badlib"]


def test_efficiency_and_speed_fall_linearly_and_unfinished_scores_zero_reliability():
    research = {"components": [], "projects": []}
    result = score_run(CASE, research, llm_calls=70, minutes=9, finished=False)
    assert result["parts"] == {"coverage": 0.0, "precision": 0.0, "efficiency": 5.0, "speed": 5.0, "reliability": 0.0}


def test_the_table_reports_an_average():
    research = {"components": [comp("piper", 3), comp("whisper", 3)], "projects": []}
    table = summary_table([score_run(CASE, research, llm_calls=30, minutes=2, finished=True)], mode="fixture")
    assert "| c | **10.0** |" in table and "**Average: 10.0**" in table


def test_the_harness_runs_a_case_offline():
    from evaluation.run_eval import CASES, run_case
    result = run_case(CASES[0], fixture=True)
    assert result["finished"] and result["parts"]["reliability"] == 10.0 and result["components"] > 0
