"""
Sorting a license text into a family the eligibility gate can reason about.

Families
    permissive       MIT, Apache, BSD, ISC, Zlib, Unlicense, CC0, PSF ...
    weak_copyleft    LGPL, MPL, EPL, CDDL: usable as a library, with conditions
    strong_copyleft  GPL, AGPL, SSPL, EUPL, OSL: copyleft reaches your code
    non_open         "commercial", "proprietary", "fair source", BUSL ...
    unknown          anything else (a pointer to a file, an unknown name)

Why it is plain text matching
    Registries write licenses in many ways ("MIT License", "Apache Software
    License", "GNU Lesser General Public License v3 or later (LGPLv3+)",
    "LGPL-3.0-only OR GPL-2.0-only"). GitHub gives SPDX ids. One small,
    testable function turns all of them into a family.

Expressions
    "A OR B": you may choose, so the most permissive option counts.
    "A AND B": all apply, so the most restrictive counts.
"""

import re
from typing import Literal

Family = Literal["permissive", "weak_copyleft", "strong_copyleft", "non_open", "unknown"]

_ORDER: dict[Family, int] = {"permissive": 0, "weak_copyleft": 1, "unknown": 2, "strong_copyleft": 3, "non_open": 4}

_PATTERNS: list[tuple[Family, re.Pattern]] = [
    ("non_open", re.compile(r"proprietary|commercial|fair ?source|busl|business source|elastic license|sspl|polyform|all rights reserved", re.I)),
    ("weak_copyleft", re.compile(r"lgpl|lesser general|library general|mpl|mozilla|\bepl\b|eclipse|cddl", re.I)),
    ("strong_copyleft", re.compile(r"agpl|affero|\bgpl|general public license|eupl|\bosl\b", re.I)),
    ("permissive", re.compile(r"\bmit\b|apache|\bbsd\b|bsd-|\bisc\b|zlib|unlicense|cc0|psf|python software|0bsd|boost|bsl-1|artistic|wtfpl|x11|ncsa", re.I)),
]


def _family_of_one(text: str) -> Family:
    for family, pattern in _PATTERNS:
        if pattern.search(text):
            return family
    return "unknown"


def license_family(text: str | None) -> Family:
    """The family of a license text, or "unknown"."""
    if not text or not text.strip() or text.strip().upper() == "NOASSERTION":
        return "unknown"
    cleaned = text.strip().strip("()")
    if re.search(r"\s+OR\s+", cleaned):
        options = [license_family(part) for part in re.split(r"\s+OR\s+", cleaned)]
        return min(options, key=lambda f: _ORDER[f])
    if re.search(r"\s+AND\s+", cleaned):
        parts = [license_family(part) for part in re.split(r"\s+AND\s+", cleaned)]
        return max(parts, key=lambda f: _ORDER[f])
    return _family_of_one(cleaned)
