"""
Writing the prompt pack (IMPLEMENTATION_GUIDE.md 8.2 to 8.4), in plain code.

Why code writes the prompts, not a model
    The model's judgement is in the roadmap: what the tasks are, their scope, their checks. Turning a task into a
    prompt is filling in a fixed template, and every field of it is required (task ids, the architecture version,
    prerequisites, license caveats, stop conditions, the review notice). Code fills it in the same way every time,
    so a caveat or a required section can never be paraphrased away. The rubric (rubric.py) still checks every
    prompt, as a guard against a future change breaking this.

How tasks become prompts
    Tasks are already in dependency order. Consecutive tasks of the same stage become ONE prompt, numbered in build
    order (01_scaffold.md, 02_data_and_storage.md ...). When the order goes back to a stage (backend work that needs
    an integration first), that stage simply gets a second, later prompt. So every task is in exactly one prompt,
    and a prompt never needs work from a later one.

The files of the pack
    README.md, PROJECT_CONTEXT.md, ARCHITECTURE.md (version and diagram), DECISIONS.md (the ADRs), CONSTRAINTS.md,
    ROADMAP.md, prompts/NN_<stage>.md, verification/acceptance-checklist.md
"""

from typing import Any

from app.models.plan import STAGE_TITLES, PromptFile, Roadmap, Task
from app.roadmap.material import approved_option, reused_facts

REVIEW_NOTICE = "Code generated from this prompt requires human review before use."
STOP_CONDITIONS = [
    "Tests still fail after two fix attempts.",
    "The work of a prerequisite prompt is missing from the repository.",
    "A component cannot be installed, or its license is not the one stated above.",
    "The task would need a dependency, service or interface that is not allowed above.",
]
SPIKE_STOP = "The spike shows that the parts do not work together as assumed: stop and report what you found, before any other task builds on it."


def allowed_dependencies(state: dict[str, Any]) -> list[str]:
    """What a prompt may depend on: the components the approved option reuses, and the stack the person named."""
    option = approved_option(state) or {}
    found = [fact["repo"] or fact["name"] for fact in reused_facts(state, option)]
    found += list((state.get("brief") or {}).get("stack_preferences", []))
    return list(dict.fromkeys(item for item in found if item))


def license_line(fact: dict[str, Any]) -> str:
    license_ = fact.get("license") or "no license found"
    reasons = "; ".join(fact.get("eligibility_reasons") or [])
    status = fact.get("eligibility") or "unresolved"
    return f"{fact['name']} ({fact.get('repo') or 'no repository'}): license {license_}; eligibility {status}" + (f" ({reasons})" if reasons else "")


def groups(roadmap: Roadmap) -> list[list[Task]]:
    """Consecutive tasks of the same stage, in build order."""
    found: list[list[Task]] = []
    for task in roadmap.tasks:
        if found and found[-1][-1].stage == task.stage:
            found[-1].append(task)
        else:
            found.append([task])
    return found


def _bullets(items: list[str], empty: str) -> str:
    return "\n".join(f"- {item}" for item in items) if items else f"- {empty}"


def _excerpt(option: dict[str, Any]) -> str:
    parts = [option.get("summary") or ""]
    for key, label in (("integration_boundaries", "Boundaries"), ("data_flow", "Data flow")):
        if option.get(key):
            parts.append(f"{label}: {option[key]}")
    return " ".join(p.strip() for p in parts if p and p.strip())


def render_prompt(number: int, total: int, tasks: list[Task], state: dict[str, Any], roadmap: Roadmap,
                  earlier: dict[str, str]) -> PromptFile:
    """One staged prompt. `earlier` maps every task id placed in an earlier prompt to that prompt's path."""
    option = approved_option(state) or {}
    stage = tasks[0].stage
    path = f"prompts/{number:02d}_{stage}.md"
    ids = [task.id for task in tasks]
    here = set(ids)
    prerequisite_paths = list(dict.fromkeys(earlier[p] for task in tasks for p in task.prerequisites if p not in here and p in earlier))
    brief = state.get("brief") or {}
    requirements = {r["id"]: r["text"] for r in brief.get("must_have", []) + brief.get("nice_to_have", [])}
    wanted = list(dict.fromkeys(r for task in tasks for r in task.requirement_ids))
    facts = {fact["name"]: fact for fact in reused_facts(state, option)}
    touched = [facts[name] for name in dict.fromkeys(c for task in tasks for c in task.components) if name in facts]
    evidence_urls = {item["id"]: item.get("url") for item in state.get("evidence", [])}
    evidence = list(dict.fromkeys(e for task in tasks for e in task.evidence_ids))
    elsewhere = [task.id for task in roadmap.tasks if task.id not in here]
    constraints = (brief.get("constraints") or {}).get("stated", [])
    version = f"{roadmap.architecture.id} version {roadmap.architecture.version}"
    allowed = allowed_dependencies(state)

    scope_blocks = []
    for task in tasks:
        block = [
            f"### {task.id} {task.title}" + (" (spike)" if task.kind == "spike" else ""),
            f"Goal: {task.goal}",
            task.scope,
            f"Likely files or modules: {', '.join(task.likely_files) or 'decide from the repository'}",
            f"Interfaces to preserve: {', '.join(task.interfaces_to_preserve) or 'none yet'}",
            "Acceptance criteria:", _bullets(task.acceptance_criteria, "none given (see the stop conditions)"),
            "Out of scope:", _bullets(task.out_of_scope, "anything not named in this task"),
        ]
        if task.validates:
            block.insert(2, f"Settles: {', '.join(task.validates)} (validation tasks of the architecture)")
        scope_blocks.append("\n".join(block))

    verification = list(dict.fromkeys(step for task in tasks for step in task.validation_steps))
    risks = list(dict.fromkeys(risk for task in tasks for risk in task.risks))
    stops = STOP_CONDITIONS + ([SPIKE_STOP] if any(task.kind == "spike" for task in tasks) else [])

    content = f"""# Prompt {number:02d} of {total:02d}: {STAGE_TITLES[stage]}

Task: {', '.join(ids)}. {'; '.join(task.title for task in tasks)}

Context:
Approved architecture {version} ("{option.get('name') or 'unnamed'}"), drafted from brief version {roadmap.brief_version}.
Relevant excerpt: {_excerpt(option)}
Milestone: {STAGE_TITLES[stage]} (prompt {number} of {total}).
Prerequisite prompts: {', '.join(prerequisite_paths) if prerequisite_paths else 'none'}.
Assumed repository state: {'the work of the prerequisite prompts is done and its tests pass' if prerequisite_paths or number > 1 else 'a new, empty repository'}.

Requirements:
{_bullets([f'{r}: {requirements[r]}' for r in wanted if r in requirements], 'none directly; this prompt prepares later work')}

Scope:
{chr(10).join(scope_blocks)}

Out of scope for this prompt: the tasks of the other prompts ({', '.join(elsewhere) or 'none'}).

Constraints:
- Do not add dependencies outside: {', '.join(allowed) if allowed else 'none (the standard library of the chosen language only)'}
- Do not modify unrelated modules
- Do not log secrets or private content
{_bullets(constraints, 'No further limits were stated in the brief.')}
- License caveats:
{_bullets([license_line(fact) for fact in touched], 'No reused component is touched by this prompt.')}

Evidence:
{_bullets([f'{e}: {evidence_urls.get(e) or "address not recorded"}' for e in evidence], 'No evidence is attached: these tasks write new code.')}

Before editing:
Inspect the repository and compare it with the assumed structure.
If a significant mismatch exists, stop and report it.
Use only the documented interfaces of the components named above. Read a component's own documentation before calling
it; do not assume an interface that is not documented.

Verification:
Add and run:
{_bullets(verification, 'no tests were planned (see the stop conditions)')}

Known risks:
{_bullets(risks, 'none recorded')}

Stop conditions:
{_bullets(stops, '')}

Completion report:
List changed files, tests actually run, results, and unresolved issues.
Do not claim a test passed unless it was executed.

Review notice:
{REVIEW_NOTICE}
"""
    return PromptFile(path=path, title=f"{number:02d} {STAGE_TITLES[stage]}", kind="prompt", content=content,
                      task_ids=ids, prerequisites=prerequisite_paths)


def render_prompts(roadmap: Roadmap, state: dict[str, Any]) -> list[PromptFile]:
    found: list[PromptFile] = []
    earlier: dict[str, str] = {}
    batches = groups(roadmap)
    for number, tasks in enumerate(batches, start=1):
        prompt = render_prompt(number, len(batches), tasks, state, roadmap, earlier)
        found.append(prompt)
        earlier.update({task.id: prompt.path for task in tasks})
    return found


# --- The context files --------------------------------------------------------------------------------------------


def _context_files(roadmap: Roadmap, state: dict[str, Any], prompts: list[PromptFile], fixture_services: list[str]) -> list[PromptFile]:
    option = approved_option(state) or {}
    brief = state.get("brief") or {}
    version = f"{roadmap.architecture.id} version {roadmap.architecture.version}"
    constraints = brief.get("constraints") or {}
    facts = reused_facts(state, option)

    fixture_notice = (
        f"\n**FIXTURE MODE: {', '.join(fixture_services)} answered from recorded fixtures, not live services.** "
        "This pack shows how Archway works; it is not a real plan.\n" if fixture_services else ""
    )
    readme = f"""# Build pack: {option.get('name') or roadmap.architecture.id}

Generated by Archway for approved architecture {version}, from brief version {roadmap.brief_version}.
{fixture_notice}
How to use it
1. Read PROJECT_CONTEXT.md, ARCHITECTURE.md, DECISIONS.md and CONSTRAINTS.md.
2. Give the prompts in prompts/ to a coding agent ONE AT A TIME, in number order. Each prompt lists its prerequisites.
3. After each prompt, check its completion report and run its verification yourself.
4. Tick the items in verification/acceptance-checklist.md as they pass.

{REVIEW_NOTICE.replace('this prompt', 'these prompts')}

Prompts
{_bullets([f'{p.path}: {", ".join(p.task_ids)}' for p in prompts], 'none')}
"""
    context = f"""# Project context

Problem: {brief.get('problem') or 'Not stated'}
Who it is for: {brief.get('users') or 'Not stated'}

Must have
{_bullets([f"{r['id']}: {r['text']}" for r in brief.get('must_have', [])], 'none')}

Nice to have
{_bullets([f"{r['id']}: {r['text']}" for r in brief.get('nice_to_have', [])], 'none')}

Assumptions (Archway assumed these; they were not said)
{_bullets([a['text'] for a in brief.get('assumptions', [])], 'none')}

Unknowns
{_bullets(brief.get('unknowns', []), 'none')}
"""
    components = "\n".join(
        f"| {c['name']} | {c['kind']} | {c.get('repo') or '-'} | {c['responsibility']} |" for c in option.get("components", [])
    )
    sections = [
        (label, option.get(key)) for key, label in (
            ("integration_boundaries", "Integration boundaries"), ("data_flow", "Data flow"), ("storage_model", "Storage"),
            ("deployment", "Deployment"), ("security_privacy", "Security and privacy"), ("testing_approach", "Testing"))
    ]
    architecture = f"""# Architecture: {option.get('name') or roadmap.architecture.id}

Version: {version} (approved). Brief version: {roadmap.brief_version}.

{option.get('summary') or ''}

Trade-off: {option.get('trade_off') or 'not stated'}

| Component | Reuse or build | Repository | Responsibility |
|---|---|---|---|
{components}

""" + "\n\n".join(f"## {label}\n{text}" for label, text in sections if text) + (
        f"\n\n## Diagram\n\n```mermaid\n{option['mermaid']}\n```\n" if option.get("mermaid") else "\n"
    ) + f"""
## Risks
{_bullets(option.get('risks', []), 'none recorded')}

## To validate before relying on it
{_bullets(option.get('validation_tasks', []), 'nothing open')}
"""
    decisions = "# Decisions\n\n" + "\n\n".join(
        f"## {d.id}: {d.title}\n\nContext: {d.context}\n\nDecision: {d.decision}\n\nRejected alternatives:\n"
        + _bullets([f"{r.option}: {r.why}" for r in d.rejected], "none were offered")
        + (f"\n\nConsequences: {d.consequences}" if d.consequences else "")
        + f"\n\nWritten by: {'Archway, from the compared options' if d.source == 'options' else 'the planning model'}"
        for d in roadmap.decisions
    ) + "\n"
    limits = [f"{label}: {constraints[key]}" for key, label in (("budget", "Budget"), ("privacy", "Privacy"), ("deployment", "Deployment")) if constraints.get(key)]
    constraint_file = f"""# Constraints

Stated by the person (hard limits)
{_bullets(constraints.get('stated', []) + limits, 'none stated')}

Allowed dependencies
{_bullets(allowed_dependencies(state), 'none beyond the standard library of the chosen language')}

Reused components and their license caveats
{_bullets([license_line(f) for f in facts], 'no component is reused')}

Forbidden
- Adding a dependency, service or paid API that is not allowed above
- Logging secrets or private content
- Claiming a test passed without running it
"""
    rows = "\n".join(
        f"| {t.id} | {t.title}{' (spike)' if t.kind == 'spike' else ''} | {STAGE_TITLES[t.stage]} | {', '.join(t.prerequisites) or '-'} | {', '.join(t.requirement_ids) or '-'} |"
        for t in roadmap.tasks
    )
    roadmap_file = f"""# Roadmap

Built for {version}. Tasks are in build order: every prerequisite comes first.

| Task | Title | Stage | Prerequisites | Requirements |
|---|---|---|---|---|
{rows}
"""
    checklist = "# Acceptance checklist\n\n" + "\n\n".join(
        f"## {t.id} {t.title}\n" + "\n".join(f"- [ ] {c}" for c in (t.acceptance_criteria or ["(no acceptance criteria were given)"]))
        for t in roadmap.tasks
    ) + "\n\n## Requirements\n" + "\n".join(
        f"- [ ] {r['id']}: {r['text']}" for r in brief.get("must_have", [])
    ) + "\n"
    return [
        PromptFile(path="README.md", title="How to use this pack", kind="context", content=readme),
        PromptFile(path="PROJECT_CONTEXT.md", title="Project context", kind="context", content=context),
        PromptFile(path="ARCHITECTURE.md", title="Architecture", kind="context", content=architecture),
        PromptFile(path="DECISIONS.md", title="Decisions", kind="context", content=decisions),
        PromptFile(path="CONSTRAINTS.md", title="Constraints", kind="context", content=constraint_file),
        PromptFile(path="ROADMAP.md", title="Roadmap", kind="context", content=roadmap_file),
        PromptFile(path="verification/acceptance-checklist.md", title="Acceptance checklist", kind="checklist", content=checklist),
    ]


def render_pack(roadmap: Roadmap, state: dict[str, Any], fixture_services: list[str] | None = None) -> list[PromptFile]:
    """Every file of the pack: the context files first, then the prompts in build order.

    `fixture_services` names the outside services that answered from recorded fixtures; the pack's README says so.
    """
    prompts = render_prompts(roadmap, state)
    return _context_files(roadmap, state, prompts, fixture_services or []) + prompts
