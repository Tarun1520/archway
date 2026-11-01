"""
Run the whole pipeline (idea to exported plan) on every sample brief, and write the results.

How to run (from backend/)
    .venv/bin/python -m evaluation.run_pipeline_eval            offline fixture mode (free; the default)
    .venv/bin/python -m evaluation.run_pipeline_eval --live     live settings from .env (spends model calls)

Writes docs/pipeline-eval-results.md and docs/pipeline-eval-results.json. Each row says whether it was a live
or fixture run. Every run uses a temporary data folder, so nothing touches your projects.
See evaluation/pipeline.py for what is measured.
"""

import json
import pathlib
import sys

from app.models.common import utc_now
from evaluation.pipeline import results_table, run_all

ROOT = pathlib.Path(__file__).resolve().parents[2]


def main() -> None:
    live = "--live" in sys.argv[1:]
    results = run_all(fixture=not live)
    table = results_table(results)
    mode = "live" if live else "fixture"
    note = (
        "Fixture runs are offline and scripted: they prove the machinery (gates, ordering, rubric, links, honest stops), "
        "not the quality of a real model's plan."
        if not live else "Live runs are not deterministic; recorded decisions are replayable from the saved receipts."
    )
    document = f"# Pipeline evaluation results\n\nRun {utc_now().date().isoformat()}, mode: **{mode}**. {note}\n\n{table}\n"
    (ROOT / "docs" / "pipeline-eval-results.md").write_text(document)
    (ROOT / "docs" / "pipeline-eval-results.json").write_text(json.dumps(results, indent=2, default=str))
    print(table)


if __name__ == "__main__":
    main()
