"""
Finding web addresses in what the user wrote.

What this file does
    Pulls URLs out of the user's own messages, so they can be read as
    "user-supplied documentation" (IMPLEMENTATION_GUIDE.md section 6.1).

What it does NOT do
    It decides nothing about safety. Every address it finds goes through the
    safe fetcher (app/research/safe_fetch.py), which may refuse it. A refused
    address is kept and shown, so nothing disappears silently.
"""

import re

_URL = re.compile(r"https?://[^\s<>\"'`]+", re.IGNORECASE)
_TRAILING = ".,;:!?)]}>"

MAX_USER_URLS = 3


def find_urls(texts: list[str]) -> list[str]:
    """Every URL in the texts, in order, once each, capped."""
    found: list[str] = []
    for text in texts:
        if text.startswith("Answer about "):
            continue  # answers to questions are not where people paste links
        for match in _URL.findall(text):
            url = match.rstrip(_TRAILING)
            if url and url not in found:
                found.append(url)
            if len(found) == MAX_USER_URLS:
                return found
    return found
