"""
Making a model-written Mermaid diagram safe to draw.

Why this exists
    A diagram's source is text a MODEL wrote. The page draws it, so it must not be able to carry a script,
    a link, or HTML. Two layers protect the page: this check (a strict allow-shape and a deny list), and the
    page's own drawing in Mermaid's "strict" security mode. If this check refuses a diagram, the option simply
    has no diagram (and says so): it never fails the whole option.

What is accepted
    a plain `flowchart` or `graph` diagram, at most 60 lines and 3,000 characters, with none of the things in
    DENIED (HTML tags, links, click handlers, init directives, scripts).
"""

import re

MAX_CHARS = 3000
MAX_LINES = 60
FIRST_LINE = re.compile(r"^(flowchart|graph)\s+(TD|TB|LR|RL|BT)\s*;?\s*$", re.IGNORECASE)
# Dangerous anywhere: HTML tags, script-ish schemes, links, init directives, backticks.
DENIED = re.compile(r"(<\s*/?\s*[a-z!]|javascript:|data:|https?:|%%|\bon[a-z]+\s*=|`)", re.IGNORECASE)
# Dangerous only as a STATEMENT (a line that starts with it): click handlers, callbacks, links, styling. A label that
# merely contains the word ("API call") is harmless text and is allowed.
DENIED_STATEMENTS = re.compile(r"^\s*(click|call|href|style|linkStyle|init)\b", re.IGNORECASE | re.MULTILINE)


def check_mermaid(source: str | None) -> tuple[str | None, str | None]:
    """(the diagram source if it is safe to draw, else None; and the reason it was refused, else None)."""
    if not source:
        return None, None
    text = source.strip()
    text = re.sub(r"^```(?:mermaid)?\s*|\s*```$", "", text, flags=re.IGNORECASE).strip()  # a code fence around it is fine
    if not text:
        return None, None
    if len(text) > MAX_CHARS:
        return None, f"it is longer than {MAX_CHARS} characters"
    lines = [line.rstrip() for line in text.splitlines() if line.strip()]
    if len(lines) > MAX_LINES:
        return None, f"it has more than {MAX_LINES} lines"
    if not FIRST_LINE.match(lines[0].strip()):
        return None, "it does not start as a plain flowchart (flowchart LR or graph TD)"
    found = DENIED.search(text) or DENIED_STATEMENTS.search(text)
    if found:
        return None, f"it contains '{found.group(0).strip()}', which is not allowed in a diagram"
    return "\n".join(lines), None


def safe_mermaid(source: str | None) -> str | None:
    """The diagram source if it is safe to draw, else None."""
    return check_mermaid(source)[0]
