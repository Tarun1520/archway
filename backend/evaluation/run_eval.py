"""
Run the research team on the evaluation cases and score each run.

How to run (from backend/)
    .venv/bin/python -m evaluation.run_eval                 all cases, live settings from .env
    .venv/bin/python -m evaluation.run_eval voice-bot       one case
    .venv/bin/python -m evaluation.run_eval --set=holdout   only the ideas no prompt was tuned on
    .venv/bin/python -m evaluation.run_eval --fixture       offline, scripted model (checks the harness only)

Each run uses a temporary data folder, so nothing touches your projects.
Results are printed and written to docs/eval-results.md and
docs/eval-results.json (the JSON keeps what was found and missed per case).
"""

import json
import pathlib
import sys
import tempfile
import time

from fastapi.testclient import TestClient

from app.config.settings import Settings
from app.main import create_app
from evaluation.scoring import score_run, summary_table

ROOT = pathlib.Path(__file__).resolve().parents[2]
CASES = json.loads((pathlib.Path(__file__).parent / "research_cases.json").read_text())["cases"]


def run_case(case: dict, *, fixture: bool) -> dict:
    with tempfile.TemporaryDirectory() as folder:
        overrides = {"data_dir": pathlib.Path(folder) / "data", "log_level": "WARNING", "background_research": False, "auth_enabled": False}
        if fixture:
            # No .env at all: a fixture run can never pick up a real key. The caps are then given here.
            overrides |= {"llm_mode": "fixture", "github_mode": "fixture", "jev_mode": "fixture", "_env_file": None,
                          "max_llm_calls_per_run": 80, "max_jev_calls_per_run": 60}
        settings = Settings(**overrides)
        with TestClient(create_app(settings)) as client:
            project = client.post("/api/projects", json={"name": case["id"], "idea": case["idea"]}).json()
            client.post(f"/api/projects/{project['id']}/messages", json={"content": case["idea"]})
            run_id = client.post(f"/api/projects/{project['id']}/runs").json()["id"]
            state = client.post(f"/api/runs/{run_id}/start").json()
            if state.get("waiting_for") and state["waiting_for"]["node"] == "clarify":
                client.post(f"/api/runs/{run_id}/clarify", json={"continue_with_assumptions": True})
            started = time.monotonic()
            state = client.post(f"/api/runs/{run_id}/confirm", json={"action": "approve"}).json()
            minutes = (time.monotonic() - started) / 60
            research = client.get(f"/api/runs/{run_id}/research").json()
    calls = next((u["calls"] for u in state.get("usage", []) if u["service"] == "llm"), 0)
    result = score_run(case, research, llm_calls=calls, minutes=minutes, finished=bool(research.get("finished")))
    # Phase 4, reported (not scored yet): the gate's verdicts and how many decisions were answered.
    verdicts = research.get("eligibility", [])
    receipts = research.get("receipts", [])
    result["eligibility"] = {s: sum(1 for v in verdicts if v["status"] == s) for s in ("eligible", "review_required", "unresolved", "excluded")}
    result["decisions"] = {"asked": len(receipts), "answered": sum(1 for r in receipts if r.get("final_result")),
                           "engine": next((r["jev_model_id"] for r in receipts if r.get("jev_model_id")), None)}
    result["examples"] = [{"component": next((c["name"] for c in research.get("components", []) if c["id"] == v["component_id"]), v["component_id"]),
                           "status": v["status"], "why": v["reasons"]} for v in verdicts[:12]]
    return result


def main(argv: list[str]) -> None:
    fixture = "--fixture" in argv
    only = next((a.split("=", 1)[1] for a in argv if a.startswith("--set=")), None)  # --set=holdout
    wanted = [a for a in argv if not a.startswith("--")]
    cases = [c for c in CASES if (not wanted or c["id"] in wanted) and (only is None or c.get("set", "tuned") == only)]
    results = []
    for case in cases:
        print(f"running {case['id']} ...", flush=True)
        result = run_case(case, fixture=fixture)
        print(f"  score {result['score']}  parts {result['parts']}  missed {[m['what'] for m in result['missed']]}", flush=True)
        print(f"  eligibility {result['eligibility']}  decisions {result['decisions']}", flush=True)
        results.append(result)
    mode = "fixture (scripted model, recorded data)" if fixture else "live"
    table = summary_table(results, mode=mode)
    print("\n" + table)
    if not fixture:
        docs = ROOT / "docs"
        docs.mkdir(exist_ok=True)
        if len(results) == len(CASES):  # only a full run replaces the published table
            (docs / "eval-results.md").write_text("# Research evaluation results\n\n" + table)
            (docs / "eval-results.json").write_text(json.dumps(results, indent=2))


if __name__ == "__main__":
    main(sys.argv[1:])
