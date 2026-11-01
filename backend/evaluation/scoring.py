"""
Scoring one research run against its evaluation case. Pure functions, no I/O.

How a run is scored (each part 0 to 10, then averaged)
    coverage    share of must-find groups that a building block or similar
                project satisfies (reference-only components do not count)
    precision   share of shown components judged fit 2 or 3 by the relevance
                judge, with any must-not hit counted as a miss
    efficiency  model calls: 10 at 40 or fewer, falling to 0 at 100
    speed       minutes of research: 10 at 4 or fewer, falling to 0 at 14
    reliability 10 if the run finished, 0 if it did not

Why these: they are the things a reviewer of the research would check, and
each is a number anyone can recompute from the saved research.
"""

from typing import Any


def _matches(alias: str, component: dict[str, Any]) -> bool:
    alias = alias.lower()
    facts = component.get("facts") or {}
    haystack = " ".join([component.get("name", ""), facts.get("reference", ""), facts.get("url", "")]).lower()
    return alias in haystack


def _building_blocks(research: dict[str, Any]) -> list[dict[str, Any]]:
    """Components that count: not judged reference-only. Similar projects count too (as references to learn from)."""
    blocks = [c for c in research.get("components", []) if c.get("fit") is None or c.get("fit", 0) >= 2]
    return blocks + [{"name": p.get("name", ""), "facts": p.get("facts") or {}} for p in research.get("projects", [])]


def _linear(value: float, best: float, worst: float) -> float:
    """10 at `best` or better, 0 at `worst` or worse, straight line between."""
    if value <= best:
        return 10.0
    if value >= worst:
        return 0.0
    return round(10.0 * (worst - value) / (worst - best), 1)


def score_run(case: dict[str, Any], research: dict[str, Any], *, llm_calls: int, minutes: float, finished: bool) -> dict[str, Any]:
    blocks = _building_blocks(research)
    found, missed = [], []
    for group in case["must_find"]:
        hit = next((c for c in blocks for alias in group["any_of"] if _matches(alias, c)), None)
        (found if hit else missed).append({"what": group["what"], "by": hit.get("name") if hit else None})

    shown = research.get("components", [])
    bad = [c for c in shown for alias in case.get("must_not", []) if _matches(alias, c)]
    judged = [c for c in shown if c.get("fit") is not None]
    good = [c for c in judged if c["fit"] >= 2 and c not in bad]
    coverage = 10.0 * len(found) / max(1, len(case["must_find"]))
    precision = 10.0 * len(good) / max(1, len(judged)) if judged else 0.0

    parts = {
        "coverage": round(coverage, 1),
        "precision": round(precision, 1),
        "efficiency": _linear(llm_calls, 40, 100),
        "speed": _linear(minutes, 4, 14),
        "reliability": 10.0 if finished else 0.0,
    }
    return {
        "case": case["id"], "set": case.get("set", "tuned"), "parts": parts, "score": round(sum(parts.values()) / len(parts), 1),
        "found": found, "missed": missed, "must_not_hits": [c.get("name") for c in bad],
        "components": len(shown), "llm_calls": llm_calls, "minutes": round(minutes, 1), "finished": finished,
    }


def summary_table(results: list[dict[str, Any]], *, mode: str) -> str:
    """A Markdown table for docs/eval-results.md."""
    lines = [
        f"Mode: {mode}. Each part is 0 to 10 (see backend/evaluation/scoring.py).", "",
        "| Case | Score | Coverage | Precision | Efficiency | Speed | Reliability | Calls | Minutes | Missed |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        p = r["parts"]
        missed = ", ".join(m["what"] for m in r["missed"]) or "none"
        lines.append(f"| {r['case']} | **{r['score']}** | {p['coverage']} | {p['precision']} | {p['efficiency']} | "
                     f"{p['speed']} | {p['reliability']} | {r['llm_calls']} | {r['minutes']} | {missed} |")
    if results:
        avg = round(sum(r["score"] for r in results) / len(results), 1)
        lines += ["", f"**Average: {avg}**"]
        for name in ("tuned", "holdout"):
            group = [r for r in results if r.get("set") == name]
            if group and len(group) < len(results):
                lines.append(f"- {name} cases ({len(group)}): {round(sum(r['score'] for r in group) / len(group), 1)}")
    return "\n".join(lines) + "\n"
