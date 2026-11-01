"""
Source-to-decision links (Checkpoint 6): from each requirement to the work, the parts, the verdicts and the sources.

    requirement  ->  how the approved option covers it
                 ->  the roadmap tasks that deliver it
                 ->  the components those tasks touch (reuse or build)
                 ->  for a reused one: its eligibility verdict, WHO decided it (rules or the decision model),
                     the ids of the decision receipts about it, and its evidence (id and address)

Everything here is copied from the run's own records. Nothing is summarised by a model.
"""

from typing import Any

from app.models.plan import PlanLink, Roadmap
from app.options.material import verdicts_by_component
from app.roadmap.material import approved_option


def build_links(roadmap: Roadmap, state: dict[str, Any]) -> list[PlanLink]:
    option = approved_option(state) or {}
    brief = state.get("brief") or {}
    parts = {part["name"]: part for part in option.get("components", [])}
    verdicts = verdicts_by_component(state.get("eligibility", []))
    urls = {item["id"]: item.get("url") for item in state.get("evidence", [])}
    receipts: dict[str, list[str]] = {}
    for receipt in state.get("receipts", []):
        receipts.setdefault(receipt["candidate_id"], []).append(receipt["id"])
    facts = {c["id"]: c.get("facts", {}) for c in state.get("components", [])}

    links = []
    for requirement in brief.get("must_have", []) + brief.get("nice_to_have", []):
        tasks = [task for task in roadmap.tasks if requirement["id"] in task.requirement_ids]
        names = list(dict.fromkeys(c for task in tasks for c in task.components))
        components = []
        for name in names:
            part = parts.get(name, {})
            candidate = part.get("candidate_id")
            verdict = verdicts.get(candidate or "", {})
            evidence = (facts.get(candidate or "", {}) or {}).get("evidence_ids", []) if candidate else []
            components.append({
                "name": name, "kind": part.get("kind"), "repo": part.get("repo"), "candidate_id": candidate,
                "eligibility": verdict.get("status") if candidate else None,
                "decided_by": verdict.get("decided_by", "rules") if candidate and verdict else None,
                "receipt_ids": receipts.get(candidate or "", []),
                "evidence": [{"id": e, "url": urls.get(e)} for e in evidence],
            })
        links.append(PlanLink(
            requirement_id=requirement["id"], requirement=requirement["text"],
            coverage=(option.get("requirement_coverage") or {}).get(requirement["id"], "unknown"),
            task_ids=[task.id for task in tasks], components=components,
        ))
    return links
