"""
Checking a roadmap in plain code, before any prompt is written from it.

What is checked (IMPLEMENTATION_GUIDE.md 8.1 and Checkpoint 6)
    - Every must-have requirement maps to at least one task.
    - Every validation task of the approved option is settled by a spike (validation before the uncertain work).
    - Every task can be finished and checked: it has acceptance criteria and validation steps.
    - There is something to build at all.

Each problem is one plain sentence. They go back to the planning model once (the retry), and any that remain
are shown with the plan, which is then exported as PARTIAL.
"""

from typing import Any

from app.models.plan import Roadmap
from app.roadmap.material import approved_option, validation_tasks


def roadmap_issues(roadmap: Roadmap, state: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    if not roadmap.tasks:
        return ["The roadmap has no tasks."]

    brief = state.get("brief") or {}
    covered = {r for task in roadmap.tasks for r in task.requirement_ids}
    for requirement in brief.get("must_have", []):
        if requirement["id"] not in covered:
            issues.append(f"Must-have {requirement['id']} ('{requirement['text']}') is not covered by any task.")

    option = approved_option(state) or {}
    settled = {v for task in roadmap.tasks if task.kind == "spike" for v in task.validates}
    for key, text in validation_tasks(option).items():
        if key not in settled:
            issues.append(f"Validation task {key} ('{text}') is not settled by any spike task.")

    for task in roadmap.tasks:
        if not task.acceptance_criteria:
            issues.append(f"{task.id} '{task.title}' has no acceptance criteria.")
        if not task.validation_steps:
            issues.append(f"{task.id} '{task.title}' has no validation steps (tests or commands to run).")
    return issues
