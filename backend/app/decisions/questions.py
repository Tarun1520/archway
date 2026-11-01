"""
The typed questions Archway asks about each component, and the state it shows.

Three decision types only (IMPLEMENTATION_GUIDE.md 6.4)
    requirement_fit     one SCORE question per requirement the capability serves
    integration_risk    one CHOICE question: low, medium or high
    needs_human_review  one BOOLEAN question

Bounded and separate
    Each question is answered in isolation against the same state, so several
    share one request without being merged into a compound question.

What the state contains
    Only retrieved material: the component's facts and evidence excerpts, the
    capability it was proposed for, and the brief's stated constraints. Text
    from READMEs and registries is DATA inside the state, never part of a
    question's instructions.
"""

from typing import Any

RUBRIC_VERSION = "rubric-2026-10-16.2"
MAX_REQUIREMENTS_PER_COMPONENT = 3

FIT_SCALE = [
    "does_not_meet: nothing in the evidence shows it provides this",
    "partially_meets: it provides part of this, or only with significant work",
    "meets: the evidence shows it provides this",
    "clearly_meets: the evidence shows it provides this directly and is a standard choice for it",
]
FIT_LABELS = [line.split(":")[0] for line in FIT_SCALE]

RISK_OPTIONS = {
    "low": "mature, maintained, permissively licensed, and a direct fit for the stated stack",
    "medium": "usable, but with notable unknowns: maintenance, adoption, licensing conditions, or stack friction",
    "high": "early-stage, unmaintained, unclear license, or a poor fit for the stated stack or constraints",
}


def questions_for(component: dict[str, Any], requirements: list[dict[str, str]]) -> dict[str, dict[str, Any]]:
    """{question name: question}. Names encode the type and requirement, so answers map back to receipts.

    LEARNING NOTE: short yes/no questions, measured
      Laya (a small decision model) was at chance with a four-step score
      question (7 of 14 right) but got 13 of 14 right with a yes/no question
      over the same evidence. So requirement fit is asked as yes/no, and the
      risk choice has three short options.
    """
    questions: dict[str, dict[str, Any]] = {}
    for req in requirements[:MAX_REQUIREMENTS_PER_COMPONENT]:
        questions[f"fit__{req['id']}"] = {
            "type": "boolean",
            "instructions": f"This component provides the following: {req['text'][:200]}.",
        }
    questions["risk"] = {
        "type": "choice",
        "instructions": "How risky is it to build on this component in this project?",
        "criteria": {"low": "mature, maintained, permissive license", "medium": "some unknowns about maintenance or license",
                     "high": "early-stage, unmaintained, or unclear license"},
    }
    questions["review"] = {
        "type": "boolean",
        "instructions": "The evidence about this component is thin or raises a licensing or maintenance concern.",
    }
    return questions


def state_for(component: dict[str, Any], capability: dict[str, Any], constraints: list[str],
              excerpts: list[str]) -> dict[str, Any]:
    facts = component["facts"]
    return {
        "component": {
            "name": component["name"], "source": f"{facts['kind']}:{facts['reference']}", "url": facts.get("url"),
            "description": facts.get("description"), "license": facts.get("license") or facts.get("license_status"),
            "archived": facts.get("archived"), "stars": facts.get("stars"),
            "downloads_last_month": facts.get("downloads_last_month"), "last_activity": facts.get("last_activity"),
        },
        "capability": {"name": capability["name"], "need": capability["need"], "approach": component.get("approach")},
        "project_constraints": constraints[:6],
        # Short on purpose: small decision models do best with focused evidence (about 512 to 1,024 tokens).
        "evidence_excerpts": [e[:500] for e in excerpts[:2]],
    }
