"""
What a tool call is about, in a few words, for the studio's "thinking" line.

What this file does
    `action_subject(args)` looks at a tool call's (already validated)
    arguments and returns:
        about   the subject in a few words: the search words, the repository,
                the package, the page ("speech to text", "openai/whisper")
        count   how many things it reports, for tools that hand in a list
                (5 components, 3 capabilities)
    The studio turns these into plain sentences like
    "Looking on GitHub for “speech to text”".

Why it is general, not per tool
    It reads a few common argument NAMES (query, repo, name, topic, text,
    url), so a new tool that uses one of them is described with no change
    here. Nothing about any kind of product is written into it.

The safety rule
    The words come from the model's own arguments, which may echo text it read
    on the web. They are only ever SHOWN as plain text, shortened, never
    followed as instructions and never put into a prompt.
"""

from typing import Any

from pydantic import BaseModel

# Argument names that hold the subject, most telling first.
SUBJECT_FIELDS = ("query", "repo", "name", "topic", "text", "url")
MAX_LENGTH = 80


def _short(text: str) -> str:
    clean = " ".join(text.split())
    clean = clean.removeprefix("https://").removeprefix("http://").removeprefix("www.")
    return clean if len(clean) <= MAX_LENGTH else clean[: MAX_LENGTH - 1].rstrip() + "…"


def action_subject(args: BaseModel) -> dict[str, Any]:
    """{"about": str | None, "count": int | None} for one tool call."""
    values = args.model_dump()
    about = next((_short(values[f]) for f in SUBJECT_FIELDS if isinstance(values.get(f), str) and values[f].strip()), None)
    count = next((len(v) for v in values.values() if isinstance(v, list) and v and not isinstance(v[0], str)), None)
    if count is None:
        # A list of plain strings (for example capability ids) still says how many.
        count = next((len(v) for v in values.values() if isinstance(v, list) and v), None)
    return {"about": about, "count": count}
