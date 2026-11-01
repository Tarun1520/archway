"""
The prompt quality rubric (IMPLEMENTATION_GUIDE.md 8.5), as plain code.

    Criterion                       Passes when
    Maps to a roadmap task          the prompt names task ids, and every one of them is in the roadmap
    References architecture version the approved option's id and version are in the prompt
    Prerequisites clear             it lists its prerequisite prompts (or "none"), and every task it depends on is
                                    in this prompt or a listed earlier one
    Bounded scope                   one stage only, and every task has explicit exclusions
    Verifiable                      every task has at least one test or command to run
    No invented APIs                no install command names a package outside the allowed dependencies, and no
                                    component that research found NOT reusable is named
    Caveats preserved               every reused component the prompt touches has its license line
    Review notice                   the notice that generated code needs human review is present

Its honest limit
    "No invented APIs" checks NAMES (packages, repositories). It cannot know whether a function a coding agent
    will call exists; the prompt tells the agent to read each component's own documentation first, and the
    manual spot check remains a person's job.

Plus one check over the whole pack: every roadmap task is in exactly one prompt.
"""

import re
from typing import Any

from app.models.plan import PromptFile, Roadmap, RubricCheck
from app.options.material import latest_by_id, reusable_components
from app.promptgen.render import REVIEW_NOTICE, allowed_dependencies, license_line
from app.roadmap.material import approved_option, reused_facts

# "pip install x", "npm install x", "npm i x", "yarn add x", "pnpm add x", "cargo add x", "go get x", "poetry add x", "uv add x"
INSTALL = re.compile(r"\b(?:pip3?\s+install|npm\s+(?:install|i)|yarn\s+add|pnpm\s+(?:add|install)|cargo\s+add|go\s+get|poetry\s+add|uv\s+(?:add|pip\s+install))\s+([^\n`;&|]+)", re.IGNORECASE)


def _package_names(arguments: str) -> list[str]:
    names = []
    for word in arguments.split():
        if word.startswith("-") or word in {".", "-e"}:
            continue
        names.append(re.split(r"[=<>@\[~^]", word.strip("'\""), maxsplit=1)[0].lower() if not word.startswith("@") else word.lower())
    return [n for n in names if n]


def _allowed_words(state: dict[str, Any]) -> set[str]:
    """Every spelling a permitted dependency may appear under: 'owner/name', 'name', and the stack words."""
    found: set[str] = set()
    for item in allowed_dependencies(state):
        lowered = item.lower()
        found |= {lowered, lowered.split("/")[-1]}
        found |= set(re.findall(r"[a-z0-9][a-z0-9._-]*", lowered))
    return found


def _not_reusable_names(state: dict[str, Any]) -> set[str]:
    """Researched components that may NOT be used (excluded, or not eligible), minus anything the option uses."""
    reusable = reusable_components(state)
    option = approved_option(state) or {}
    used = {(f.get("repo") or "").lower() for f in reused_facts(state, option)} | {f["name"].lower() for f in reused_facts(state, option)}
    names = set()
    for component in latest_by_id(state.get("components", [])):
        if component["id"] in reusable:
            continue
        reference = ((component.get("facts") or {}).get("reference") or "").lower()
        for name in (reference, component.get("name", "").lower()):
            if name and len(name) > 3 and name not in used:
                names.add(name)
    return names


def check_prompt(prompt: PromptFile, roadmap: Roadmap, state: dict[str, Any], placed_before: set[str]) -> list[RubricCheck]:
    """Every rubric line for one prompt. `placed_before` holds the task ids of all earlier prompts."""
    tasks = {task.id: task for task in roadmap.tasks}
    mine = [tasks[t] for t in prompt.task_ids if t in tasks]
    text = prompt.content
    checks: list[RubricCheck] = []

    unknown = [t for t in prompt.task_ids if t not in tasks]
    named = bool(prompt.task_ids) and all(f"{t}" in text.split("Context:")[0] for t in prompt.task_ids)
    checks.append(RubricCheck(criterion="Maps to a roadmap task", passed=named and not unknown,
                              detail=f"unknown task ids: {', '.join(unknown)}" if unknown else None if named else "no task id in the Task line"))

    version = f"{roadmap.architecture.id} version {roadmap.architecture.version}"
    checks.append(RubricCheck(criterion="References architecture version", passed=version in text,
                              detail=None if version in text else f"'{version}' is missing"))

    listed = "Prerequisite prompts:" in text
    missing = sorted({p for task in mine for p in task.prerequisites if p not in prompt.task_ids and p not in placed_before})
    checks.append(RubricCheck(criterion="Prerequisites clear", passed=listed and not missing,
                              detail=("needs work from a later prompt: " + ", ".join(missing)) if missing else None if listed else "no prerequisite line"))

    stages = {task.stage for task in mine}
    no_exclusions = [task.id for task in mine if not task.out_of_scope]
    bounded = len(stages) == 1 and not no_exclusions and "Out of scope" in text
    checks.append(RubricCheck(criterion="Bounded scope", passed=bounded,
                              detail=None if bounded else ("more than one stage" if len(stages) > 1 else f"no explicit exclusions for {', '.join(no_exclusions) or 'the prompt'}")))

    unverified = [task.id for task in mine if not task.validation_steps]
    checks.append(RubricCheck(criterion="Verifiable", passed=bool(mine) and not unverified,
                              detail=f"no test or command for {', '.join(unverified)}" if unverified else None))

    # Only what the planner wrote is scanned: the brief's own words may name a tool the person mentioned.
    written = "\n".join(
        part for task in mine
        for part in [task.title, task.goal, task.scope, *task.acceptance_criteria, *task.validation_steps, *task.likely_files, *task.risks]
    )
    allowed = _allowed_words(state)
    installs = [name for match in INSTALL.finditer(written) for name in _package_names(match.group(1))]
    outside = sorted({name for name in installs if name.lower() not in allowed})
    lowered = written.lower()
    forbidden = sorted(name for name in _not_reusable_names(state) if re.search(rf"(?<![\w/-]){re.escape(name)}(?![\w/-])", lowered))
    invented = outside + [f"{name} (not reusable)" for name in forbidden]
    checks.append(RubricCheck(criterion="No invented APIs", passed=not invented,
                              detail=("names something not allowed: " + ", ".join(invented)) if invented else "package and repository names checked"))

    option = approved_option(state) or {}
    facts = {fact["name"]: fact for fact in reused_facts(state, option)}
    needed = [facts[c] for task in mine for c in task.components if c in facts]
    dropped = [fact["name"] for fact in needed if license_line(fact) not in text]
    checks.append(RubricCheck(criterion="Caveats preserved", passed=not dropped,
                              detail=f"license caveat missing for {', '.join(dropped)}" if dropped else None))

    checks.append(RubricCheck(criterion="Review notice", passed=REVIEW_NOTICE in text,
                              detail=None if REVIEW_NOTICE in text else "the review notice is missing"))
    return checks


def check_pack(files: list[PromptFile], roadmap: Roadmap, state: dict[str, Any]) -> tuple[list[PromptFile], list[str]]:
    """The files with their rubric filled in, and every failure as a sentence (for the retry and the notes)."""
    checked: list[PromptFile] = []
    failures: list[str] = []
    placed: set[str] = set()
    counts: dict[str, int] = {}
    for file in files:
        if file.kind != "prompt":
            checked.append(file)
            continue
        rubric = check_prompt(file, roadmap, state, placed)
        checked.append(file.model_copy(update={"rubric": rubric}))
        failures += [f"{file.path}: {r.criterion} failed ({r.detail})" for r in rubric if not r.passed]
        placed |= set(file.task_ids)
        for task_id in file.task_ids:
            counts[task_id] = counts.get(task_id, 0) + 1
    for task in roadmap.tasks:
        if counts.get(task.id, 0) != 1:
            failures.append(f"{task.id} is in {counts.get(task.id, 0)} prompts; every task must be in exactly one.")
    return checked, failures
