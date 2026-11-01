"""
Keeping secrets out of anything the browser can see.

What this file does
    register_secrets([...])   remembers the real secret values from the settings (done once, at start-up)
    scrub("...")              returns the text with every known secret value, and anything shaped like a key or token,
                              replaced by "[redacted]"

Why it is needed
    Error messages from outside services are shown to the person ("the model service answered HTTP 401: ..."), and
    some services echo part of the credential back in their error text ("Incorrect API key provided: sk-ab...yz").
    Every message that leaves the backend (HTTP error answers, run events in the live stream) passes through scrub(),
    so even a service that misbehaves cannot get a key onto someone's screen. The log formatter does the same for
    log lines (app/logging_setup.py).

Its honest limit
    It recognises the key shapes listed below and the exact values in the settings. A secret of a completely unknown
    shape that is not in the settings would not be recognised; none is used today.
"""

import re

_known: list[str] = []

# Shapes of credentials: provider key prefixes, bearer tokens, key=value pairs, JWTs, and long opaque runs.
_PATTERNS = [
    re.compile(r"\b(?:sk|gsk|pk|rk)[-_][A-Za-z0-9_\-]{8,}"),  # OpenAI / Groq / Stripe-style keys
    re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}|\bgithub_pat_[A-Za-z0-9_]{20,}"),  # GitHub tokens
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._\-~+/=]{8,}"),
    re.compile(r"(?i)\b(?:api[-_ ]?key|token|secret|password|authorization)\b\s*[:=]\s*['\"]?[^\s'\",;]{6,}"),
    re.compile(r"\beyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}"),  # JWTs
    re.compile(r"\b[A-Za-z0-9_\-]{40,}\b"),  # any long opaque run (keys, hashes, session tokens)
]


def register_secrets(values: list[str | None]) -> None:
    """Remember the real secret values (only meaningful ones: 8 characters or more)."""
    _known.clear()
    _known.extend(sorted({value for value in values if value and len(value) >= 8}, key=len, reverse=True))


def scrub(text: str) -> str:
    if not text:
        return text
    for value in _known:
        text = text.replace(value, "[redacted]")
    for pattern in _PATTERNS:
        text = pattern.sub("[redacted]", text)
    return text


def scrub_data(value):
    """scrub() applied to every string inside a dict / list (for event payloads)."""
    if isinstance(value, str):
        return scrub(value)
    if isinstance(value, dict):
        return {key: scrub_data(item) for key, item in value.items()}
    if isinstance(value, list):
        return [scrub_data(item) for item in value]
    return value
