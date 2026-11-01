"""
Deciding whether two short sentences say the same thing.

What this file does
    `is_similar(a, b)` is True when one sentence is essentially contained in
    the other, ignoring filler words. "Integrate with payment gateway" and
    "The app must integrate a payment gateway for online payments" are similar.

Why it exists
    A live run showed the same requirement twice (REQ-2 and REQ-3), once
    written by the model and once added from a "mandatory integration". The
    same check also keeps suggestions from repeating what the brief already
    says.

Its honest limit
    It compares words, not meaning. It will miss a rewording that shares no
    words, and it can occasionally treat two short, different sentences as
    the same. Wrongly hiding a suggestion costs little; showing a repeat is
    what this prevents.
"""

import re

# Words that carry no meaning of their own in a requirement.
_FILLER = {
    "a", "an", "the", "and", "or", "of", "to", "for", "with", "in", "on", "at", "by", "from", "as",
    "is", "are", "be", "been", "it", "its", "that", "this", "these", "those", "which",
    "app", "application", "system", "site", "website", "tool", "project",
    "must", "should", "shall", "can", "will", "would", "need", "needs", "have", "has", "allow", "allows",
}


def _words(text: str) -> set[str]:
    return {word for word in re.findall(r"[a-z0-9]+", text.lower()) if word not in _FILLER}


def _stem(word: str) -> str:
    """A very small stemmer so "payments" matches "payment" and "integrates" matches "integrate"."""
    for ending in ("ing", "es", "s"):
        if word.endswith(ending) and len(word) - len(ending) >= 4:
            return word[: -len(ending)]
    return word


def content_words(text: str) -> set[str]:
    """The stemmed words of a sentence (the same words is_similar compares)."""
    return {_stem(word) for word in _words(text)}


def is_similar(first: str, second: str, threshold: float = 0.85) -> bool:
    """True when most of the shorter sentence's words appear in the other."""
    a = {_stem(word) for word in _words(first)}
    b = {_stem(word) for word in _words(second)}
    if not a or not b:
        return first.strip().lower() == second.strip().lower()
    # A one-word value (such as a deployment of "web") must not swallow every
    # sentence that contains that word: with so little to compare, only an
    # exact match counts.
    if min(len(a), len(b)) < 2:
        return a == b
    return len(a & b) / min(len(a), len(b)) >= threshold
