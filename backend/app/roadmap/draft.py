"""
Drafting the roadmap: the shape the model fills in, and the code that turns it into a real Roadmap.

BEHAVIOUR THIS FILE ENFORCES (the model plans, code decides)
    - Every field of the draft is required (an empty list where nothing applies), so a strict provider accepts it.
    - Task ids are made here (T-01, T-02 ... in build order). The model links tasks by its own short keys.
    - A prerequisite, requirement id, component name or validation-task id that does not exist is dropped,
      and said in a note. Nothing the model invents survives as a link.
    - Evidence ids are never the model's: a task's evidence is the evidence of the reused components it touches.
    - A spike that settles a validation task becomes a prerequisite of every other task touching the same
      components (validation before the uncertain integration), when that does not create a loop.
    - The order is a real dependency order (a topological sort). A loop in the prerequisites cannot be ordered:
      it is reported as a blocking issue, and the tasks in it are placed by stage only.
    - The first decision record (ADR-1, the architecture itself) is written by code from the compared options,
      so the rejected alternatives are the real ones. The model's decisions follow it.
"""

from typing import Any, Literal

from app.models.brief_draft import StrictModel
from app.models.option_flow import VersionRef
from app.models.plan import STAGES, Decision, RejectedAlternative, Roadmap, Task
from app.roadmap.material import alternatives, approved_option, reused_facts, validation_tasks

StageName = Literal["scaffold", "data_and_storage", "backend_features", "integrations", "frontend", "tests_and_security"]


class DraftTask(StrictModel):
    key: str  # the model's own short label, used only to link prerequisites
    title: str
    goal: str
    stage: StageName
    kind: Literal["build", "spike"]
    prerequisites: list[str]  # keys of other tasks
    scope: str
    out_of_scope: list[str]
    likely_files: list[str]
    interfaces_to_preserve: list[str]
    requirement_ids: list[str]
    components: list[str]  # names of the approved option's components
    acceptance_criteria: list[str]
    validation_steps: list[str]
    risks: list[str]
    validates: list[str]  # ids of the option's validation tasks (V-1 ...) this spike settles


class DraftRejected(StrictModel):
    option: str
    why: str


class DraftDecision(StrictModel):
    title: str
    context: str
    decision: str
    rejected: list[DraftRejected]
    consequences: str


class RoadmapDraft(StrictModel):
    tasks: list[DraftTask]
    decisions: list[DraftDecision]


def parse_draft(data: dict[str, Any]) -> RoadmapDraft:
    """Validate the model's reply. A list the model left out is empty (nothing to say), never a reason to fail."""
    data = dict(data)
    data.setdefault("decisions", [])
    lists = ("prerequisites", "out_of_scope", "likely_files", "interfaces_to_preserve", "requirement_ids", "components",
             "acceptance_criteria", "validation_steps", "risks", "validates")
    data["tasks"] = [{**{key: [] for key in lists}, **task} for task in data.get("tasks") or []]
    data["decisions"] = [{"rejected": [], **decision} for decision in data["decisions"]]
    return RoadmapDraft.model_validate(data)


def _clean(items: list[str]) -> list[str]:
    return [text.strip() for text in items if text and text.strip()]


def _reaches(edges: dict[str, set[str]], start: str, goal: str) -> bool:
    """True if `goal` can be reached from `start` by following prerequisites."""
    seen, todo = set(), [start]
    while todo:
        key = todo.pop()
        if key == goal:
            return True
        if key not in seen:
            seen.add(key)
            todo.extend(edges.get(key, ()))
    return False


def order_tasks(keys: list[str], stage_of: dict[str, str], spike: set[str], edges: dict[str, set[str]]) -> tuple[list[str], list[str]]:
    """A dependency order: (keys in order, keys caught in a loop).

    LEARNING NOTE: a topological sort (Kahn's method)
      Repeatedly take a task whose prerequisites are all placed already. When several are ready, take the one in
      the earliest stage (spikes first, then the draft's own order), so the order reads naturally. Whatever is
      left at the end is in a loop: no task in it can ever be "ready".
    """
    position = {key: index for index, key in enumerate(keys)}
    rank = lambda key: (STAGES.index(stage_of[key]), key not in spike, position[key])  # noqa: E731
    placed: list[str] = []
    waiting = set(keys)
    while waiting:
        ready = [key for key in waiting if not (edges.get(key, set()) & waiting)]
        if not ready:
            break
        chosen = min(ready, key=rank)
        placed.append(chosen)
        waiting.discard(chosen)
    looped = sorted(waiting, key=rank)
    return placed + looped, looped


def architecture_decision(state: dict[str, Any], option: dict[str, Any]) -> Decision:
    """ADR-1, written by code: the approved architecture, and the options that were compared and not chosen."""
    others = alternatives(state, option)
    rejected = [
        RejectedAlternative(option=f"{o['id']} v{o['version']} {o.get('name') or ''}".strip(),
                            why=(o.get("trade_off") or o.get("avoid_if") or "Not chosen by the person.").strip())
        for o in others
    ]
    problem = ((state.get("brief") or {}).get("problem") or "").strip() or "The project in the brief."
    return Decision(
        id="ADR-1", title=f"Architecture: {option.get('name') or option['id']}",
        context=problem,
        decision=f"Build {option['id']} version {option['version']} ({option.get('name') or 'unnamed'}): {option['summary']}",
        rejected=rejected,
        consequences=(option.get("trade_off") or "").strip() or None,
        source="options",
    )


def build_roadmap(draft: RoadmapDraft, state: dict[str, Any]) -> tuple[Roadmap, list[str], list[str]]:
    """Turn the model's draft into a Roadmap. Returns (roadmap, blocking issues, notes)."""
    option = approved_option(state)
    if option is None:
        raise ValueError("there is no approved option version to plan")
    brief = state.get("brief") or {}
    requirement_ids = {r["id"] for r in brief.get("must_have", []) + brief.get("nice_to_have", [])}
    component_names = {part["name"].strip().lower(): part["name"] for part in option.get("components", [])}
    evidence_by_component = {fact["name"]: fact["evidence_ids"] for fact in reused_facts(state, option)}
    checks = validation_tasks(option)
    issues: list[str] = []
    notes: list[str] = []

    # One task per key: a repeated key would make its prerequisites ambiguous.
    tasks: dict[str, DraftTask] = {}
    for task in draft.tasks:
        key = task.key.strip() or f"task{len(tasks) + 1}"
        if key in tasks:
            notes.append(f"The plan named two tasks '{key}'; the second was renamed.")
            key = f"{key}-{len(tasks) + 1}"
        tasks[key] = task

    edges: dict[str, set[str]] = {}
    for key, task in tasks.items():
        known = {p.strip() for p in task.prerequisites if p.strip() in tasks and p.strip() != key}
        dropped = [p for p in task.prerequisites if p.strip() not in known]
        if dropped:
            notes.append(f"Task '{task.title}' named prerequisites that do not exist ({', '.join(dropped)}); they were dropped.")
        edges[key] = known

    def touched(task: DraftTask) -> list[str]:
        return [component_names[name.strip().lower()] for name in task.components if name.strip().lower() in component_names]

    # Validation first: a spike becomes a prerequisite of every other task touching the same components.
    spikes = {key for key, task in tasks.items() if task.kind == "spike"}
    for spike in spikes:
        shared = set(touched(tasks[spike]))
        for key, task in tasks.items():
            if key == spike or key in spikes or not shared & set(touched(task)):
                continue
            if spike not in edges[key] and not _reaches(edges, spike, key):
                edges[key].add(spike)

    stage_of = {key: task.stage for key, task in tasks.items()}
    ordered, looped = order_tasks(list(tasks), stage_of, spikes, edges)
    if looped:
        issues.append("These tasks wait for each other in a loop, so they cannot be ordered: "
                      + ", ".join(f"'{tasks[key].title}'" for key in looped) + ".")
    ids = {key: f"T-{index:02d}" for index, key in enumerate(ordered, start=1)}

    built: list[Task] = []
    for key in ordered:
        task = tasks[key]
        parts = touched(task)
        unknown = [name for name in task.components if name.strip().lower() not in component_names]
        if unknown:
            notes.append(f"{ids[key]} named components that are not in the approved option ({', '.join(unknown)}); they were dropped.")
        bad_requirements = [r for r in task.requirement_ids if r not in requirement_ids]
        if bad_requirements:
            notes.append(f"{ids[key]} named requirement ids that are not in the brief ({', '.join(bad_requirements)}); they were dropped.")
        evidence = list(dict.fromkeys(e for name in parts for e in evidence_by_component.get(name, [])))
        built.append(Task(
            id=ids[key], title=task.title.strip() or ids[key], goal=task.goal.strip() or task.title.strip() or ids[key],
            stage=task.stage, kind=task.kind,
            prerequisites=[ids[p] for p in ordered if p in edges[key]],
            scope=task.scope.strip() or task.goal.strip() or task.title.strip() or ids[key],
            out_of_scope=_clean(task.out_of_scope), likely_files=_clean(task.likely_files),
            interfaces_to_preserve=_clean(task.interfaces_to_preserve),
            requirement_ids=[r for r in dict.fromkeys(task.requirement_ids) if r in requirement_ids],
            components=parts, evidence_ids=evidence,
            acceptance_criteria=_clean(task.acceptance_criteria), validation_steps=_clean(task.validation_steps),
            risks=_clean(task.risks),
            validates=[v for v in dict.fromkeys(task.validates) if v in checks] if task.kind == "spike" else [],
        ))

    decisions = [architecture_decision(state, option)]
    for number, item in enumerate(draft.decisions, start=2):
        if not (item.title.strip() and item.decision.strip()):
            continue
        decisions.append(Decision(
            id=f"ADR-{number}", title=item.title.strip(), context=item.context.strip() or item.title.strip(),
            decision=item.decision.strip(),
            rejected=[RejectedAlternative(option=r.option.strip(), why=r.why.strip()) for r in item.rejected if r.option.strip() and r.why.strip()],
            consequences=item.consequences.strip() or None, source="model",
        ))

    roadmap = Roadmap(
        architecture=VersionRef(id=option["id"], version=option["version"]),
        brief_version=option.get("brief_version") or brief.get("version") or 1,
        tasks=built, decisions=decisions,
    )
    return roadmap, issues, notes
