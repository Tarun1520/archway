"""
Spotting requirements that cannot all be true.

What this file does
    Checks a brief against a short list of known clashes, for example
    "no paid hosting" together with "everyone sees changes instantly from
    anywhere" (which needs a server that is always running).

Why plain Python
    Checkpoint 2 says "Conflicting requirements are flagged". A model may
    also suggest conflicts (the builder keeps those too), but these rules
    fire the same way every time and can be tested.

How a rule works
    Each rule has two sets of phrases. If one phrase from side A appears in
    the CONSTRAINTS and one from side B appears in the REQUIREMENTS, the rule
    reports a conflict and names the requirements involved.

Its honest limit
    Only the clashes listed in RULES are detected. Add a rule to cover more.

How it plugs in
    app/briefing/builder.py calls `find_conflicts` whenever a brief is built
    or edited, so conflicts are re-checked after every change.
"""

import re
from dataclasses import dataclass

from app.models.brief import Conflict, Constraints, Requirement


@dataclass(frozen=True)
class ConflictRule:
    name: str
    constraint_patterns: tuple[str, ...]  # side A: looked for in the constraints
    requirement_patterns: tuple[str, ...]  # side B: looked for in the requirements
    explanation: str


RULES = [
    ConflictRule(
        name="no_paid_hosting_vs_always_on",
        constraint_patterns=(r"no\s+paid", r"(don'?t|do not)\s+(want\s+to\s+)?pay", r"\bfree\b", r"no\s+(hosting|server|cost|budget)"),
        requirement_patterns=(
            r"always[- ]on", r"from\s+any(where|\s+network)", r"real[- ]?time", r"\binstant", r"within\s+seconds",
            r"at\s+the\s+same\s+time", r"simultaneous", r"live\s+sync", r"24/7", r"multi[- ]?user",
            # Not the bare word "team": "only authorized team members can use the files" needs no server at all
            # (a real run flagged it). Only a team reaching a SHARED service online counts.
            r"\bteam\b[^.]{0,60}\b(online|over\s+the\s+internet|from\s+anywhere|hosted|web\s+app|shared\s+(server|service|app))",
        ),
        explanation=(
            "A service that many people reach at any time needs a server that is always running, "
            "which usually costs money. That conflicts with the stated limit on paying for hosting, "
            "unless a server that is already owned can be used."
        ),
    ),
    ConflictRule(
        name="offline_vs_cloud",
        constraint_patterns=(r"\boffline\b", r"no\s+internet", r"without\s+(the\s+)?internet"),
        requirement_patterns=(
            r"\bcloud\b", r"hosted\s+(model|service|api)", r"sync\s+(across|between|with)", r"from\s+anywhere",
            r"\bonline\b", r"real[- ]?time\s+collaborat",
        ),
        explanation=(
            "Working offline means no network connection can be assumed, "
            "which conflicts with a requirement that depends on an online service."
        ),
    ),
    ConflictRule(
        name="data_stays_local_vs_hosted",
        constraint_patterns=(
            r"(never|not|must\s+not)\s+leave", r"stay(s)?\s+(local|on\s+my)", r"local[- ]only", r"on\s+my\s+(own\s+)?(laptop|machine|computer|device)",
        ),
        requirement_patterns=(
            r"\bcloud\b", r"hosted\s+(model|service|api)", r"\b(openai|gpt|claude|gemini)\b", r"sync\s+(across|between|with)",
            r"share\s+with", r"from\s+anywhere",
        ),
        explanation=(
            "Data that must stay on the user's own machine cannot be sent to a hosted service, "
            "which this requirement appears to need."
        ),
    ),
]


def _matches(patterns: tuple[str, ...], text: str) -> bool:
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)


def find_conflicts(constraints: Constraints, requirements: list[Requirement]) -> list[Conflict]:
    """Return one Conflict per rule that fires. An empty list means none of the rules fired."""
    # Everything that expresses a limit: the three fields plus the user's own sentences.
    constraint_text = " . ".join(
        part for part in [constraints.budget, constraints.privacy, constraints.deployment, *constraints.stated] if part
    )

    conflicts = []
    for rule in RULES:
        if not _matches(rule.constraint_patterns, constraint_text):
            continue
        involved = [item.id for item in requirements if _matches(rule.requirement_patterns, item.text)]
        if involved:
            conflicts.append(Conflict(description=rule.explanation, requirement_ids=involved))
    return conflicts
