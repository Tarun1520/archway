"""
Scripted answer for the plan stage (build_roadmap), for FIXTURE mode (offline, free, repeatable).

NOT intelligence. It lays out a fixed shape of tasks from the material in the prompt: set up the repository,
one spike per validation task, storage, one integration task per reused component, the core features (covering
every must-have), the interface, and tests. Every text says FIXTURE.

Its job is to let the whole plan stage run in tests and offline, with the same shape of answer a real model gives,
so the code around the model (ordering, checks, prompts, rubric, export) is exercised for real.
"""

import json
import re
from typing import Any

NOTE = "FIXTURE: planned by simple rules, not by a model."


def _material(user_text: str) -> dict[str, Any]:
    match = re.search(r"<material>\s*(\{.*?\})\s*</material>", user_text, re.DOTALL)
    return json.loads(match.group(1)) if match else {}


def _task(key: str, title: str, stage: str, *, kind: str = "build", prerequisites: list[str] | None = None,
          components: list[str] | None = None, requirement_ids: list[str] | None = None, validates: list[str] | None = None) -> dict[str, Any]:
    return {
        "key": key, "title": title, "goal": f"{NOTE} {title}.", "stage": stage, "kind": kind,
        "prerequisites": prerequisites or [], "scope": f"{NOTE} {title}, and nothing else.",
        "out_of_scope": ["Work that belongs to other tasks"], "likely_files": [], "interfaces_to_preserve": [],
        "requirement_ids": requirement_ids or [], "components": components or [],
        "acceptance_criteria": [f"{title}: done, and its tests pass"],
        "validation_steps": [f"Run the project's test suite after: {title.lower()}"],
        "risks": [NOTE], "validates": validates or [],
    }


def fixture_roadmap(user_text: str) -> dict[str, Any]:
    material = _material(user_text)
    option = material.get("approved_option") or {}
    parts = option.get("components") or []
    reused = [p["name"] for p in parts if p.get("kind") == "reuse"]
    built = [p["name"] for p in parts if p.get("kind") == "build"]
    must = [r["id"] for r in (material.get("brief") or {}).get("must_have", [])]

    tasks = [_task("setup", "Set up the repository and configuration", "scaffold")]
    spikes = [
        _task(f"check{n}", f"Spike: {v['text'][:80]}", "integrations", kind="spike", prerequisites=["setup"], components=reused, validates=[v["id"]])
        for n, v in enumerate(material.get("validation_tasks") or [], start=1)
    ]
    tasks += spikes
    tasks.append(_task("store", "Add the data storage", "data_and_storage", prerequisites=["setup"]))
    joins = [_task(f"use{n}", f"Integrate {name}", "integrations", prerequisites=["setup"], components=[name]) for n, name in enumerate(reused, start=1)]
    tasks += joins
    tasks.append(_task("core", "Build the core features", "backend_features", prerequisites=["store", *[t["key"] for t in joins]],
                       components=built, requirement_ids=must))
    tasks.append(_task("ui", "Build the user interface", "frontend", prerequisites=["core"]))
    tasks.append(_task("tests", "Add end-to-end tests and security checks", "tests_and_security", prerequisites=["core", "ui"]))
    return {"tasks": tasks, "decisions": []}
