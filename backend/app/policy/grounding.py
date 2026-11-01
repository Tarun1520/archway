"""
Keeping the model's guesses out of what the person asked for.

What this file does
    The model sometimes fills `stack_preferences` with tools the person never named, and then writes those tools
    into `must_have` too. Downstream, the research team treats both as requirements, so a guess steers the whole
    run (found in a real run: see docs/reviews/2026-10-19-argon-review-assessment.md). This file checks, in plain
    code, which named tools really appear in what the person wrote:

        ground_stack(stack, user_texts)    -> (kept, not_named)   the tools the person named, and the rest
        requirements_naming(must, names, user_texts)              must-haves that name a tool they did not
        restates_assumption(text, assumptions, user_texts)        a requirement that is really one of the model's
                                                                  own assumptions, written as a requirement

    The builder (app/briefing/builder.py) keeps what is grounded and moves the rest into ASSUMPTIONS, shown to the
    person as "Archway assumed this", where they can keep, edit or remove it before approving.

How a name is matched
    An entry like "Pandas for loading and cleaning data" is cut at its first joining word ("for", "as", "to",
    a comma ...), so only the NAME part is checked; "A or B" checks each alternative. A name counts as named when
    every distinctive word of it (not a generic word like "library" or "data") appears as a whole word in the
    person's text, or a known alias does ("sklearn" for "scikit-learn").

Its honest limit
    A tool the person described without naming it ("the Python data library") is not recognised, and moves to the
    assumptions. That is the safe direction: an assumption is still shown, it just is not treated as a requirement.
"""

import re

from app.briefing.similarity import content_words

CUT_AT = re.compile(r"\s+(?:for|as|to|with|which|that|is|are|in|on|via|using)\s+|[:(,;]|\s[-–—]\s", re.IGNORECASE)
ALTERNATIVES = re.compile(r"\s+(?:or|and)\s+|/", re.IGNORECASE)
WORD = re.compile(r"[a-z0-9][a-z0-9.+#-]*[a-z0-9+#]|[a-z0-9]")

GENERIC = {
    "a", "an", "the", "its", "their", "our", "your", "any", "some", "main", "primary", "basic", "simple", "standard",
    "library", "libraries", "framework", "frameworks", "package", "packages", "tool", "tools", "toolkit", "sdk", "api",
    "apis", "language", "languages", "programming", "database", "databases", "db", "service", "services", "cloud",
    "server", "servers", "platform", "platforms", "app", "apps", "application", "data", "datasets", "dataset",
    "storage", "engine", "model", "models", "module", "modules", "system", "stack", "based", "open", "source",
    "open-source", "client", "plugin", "plugins", "backend", "frontend", "web", "mobile", "local", "hosted",
}
# Spellings of the same tool. A name counts as named if the person wrote any spelling of it.
ALIASES = {
    "scikit-learn": {"sklearn", "scikit"}, "sklearn": {"scikit-learn"}, "postgresql": {"postgres"}, "postgres": {"postgresql"},
    "javascript": {"js"}, "typescript": {"ts"}, "node.js": {"node", "nodejs"}, "nodejs": {"node", "node.js"},
    "kubernetes": {"k8s"}, "react": {"reactjs", "react.js"}, "golang": {"go"}, "mongodb": {"mongo"}, "c#": {"csharp"},
}


def _words(text: str) -> set[str]:
    return set(WORD.findall(text.lower()))


def _names(entry: str) -> list[list[str]]:
    """The distinctive words of each alternative in the NAME part of an entry."""
    head = CUT_AT.split(entry.strip(), maxsplit=1)[0]
    found = []
    for alternative in ALTERNATIVES.split(head):
        words = [w for w in WORD.findall(alternative.lower()) if w not in GENERIC]
        if words:
            found.append(words)
    return found


def _said(word: str, said: set[str]) -> bool:
    return word in said or bool(ALIASES.get(word, set()) & said)


def is_named(entry: str, user_texts: list[str]) -> bool:
    said = _words(" ".join(user_texts))
    return any(all(_said(w, said) for w in words) for words in _names(entry))


def ground_stack(stack: list[str], user_texts: list[str]) -> tuple[list[str], list[str]]:
    """(entries the person named, entries they did not)."""
    kept, not_named = [], []
    for entry in stack:
        (kept if is_named(entry, user_texts) else not_named).append(entry)
    return kept, not_named


def requirements_naming(requirements: list[str], not_named: list[str], user_texts: list[str]) -> list[str]:
    """The requirements that mention one of the not-named tools by a word the person never used."""
    said = _words(" ".join(user_texts))
    tool_words = {w for entry in not_named for words in _names(entry) for w in words if not _said(w, said)}
    return [text for text in requirements if _words(text) & tool_words]


# --- Requirements that are really assumptions ----------------------------------------------------------------------
# Found in a real run: the model assumed "the decision model is some kind of numeric predictor" (an assumption, shown
# as such) and then ALSO wrote "the model will be implemented as a supervised regression model" as a must-have. The
# person never said it; the requirement just repeated the model's own guess. Two plain measures catch that, in any
# domain: most of the requirement's words are NOT the person's, and much of it repeats one of the model's assumptions.
BACKED_BELOW = 0.4  # under this share of the requirement's words appear in what the person wrote
REPEATS_FROM = 0.5  # at least this share of the shorter text's words are shared with one assumption
MIN_ASSUMPTION_WORDS = 4  # a very short assumption matches too much by accident


def restates_assumption(text: str, assumptions: list[str], user_texts: list[str]) -> bool:
    """True when a requirement is barely backed by the person's words and mostly repeats one of the assumptions."""
    words = content_words(text)
    if not words:
        return False
    said = content_words(" ".join(user_texts))
    if len(words & said) / len(words) >= BACKED_BELOW:
        return False
    for assumption in assumptions:
        other = content_words(assumption)
        if len(other) >= MIN_ASSUMPTION_WORDS and len(words & other) / min(len(words), len(other)) >= REPEATS_FROM:
            return True
    return False
