"""
Finding hard limits in the user's own words.

What this file does
    Reads what the user typed and picks out the sentences that read like
    constraints ("no paid hosting", "must work offline", "never leaves my
    laptop"). Those sentences are kept WORD FOR WORD in the brief.

Why plain Python and not the model
    Checkpoint 2 says "Stated constraints are never silently dropped". A
    model summarising text can drop or soften a limit. This detector cannot:
    if a sentence matches, it goes into the brief exactly as written, whatever
    the model returned.

Its honest limit
    It works by looking for known phrases. A constraint worded in a way the
    list below does not cover will not be found here (the model may still
    capture it). To widen the net, add a pattern to CONSTRAINT_PATTERNS.

How it plugs in
    app/briefing/builder.py calls `find_stated_constraints` every time a
    brief is built.
"""

import re

# LEARNING NOTE: regular expressions (regex)
#   A regex is a small pattern language for finding text. A few pieces used
#   below:   \b = a word boundary,  (a|b) = a or b,  ? = the thing before it
#   is optional,  \s+ = one or more spaces.  re.IGNORECASE ignores capitals.
CONSTRAINT_PATTERNS = [
    r"\bno\s+paid\b",
    r"\b(don'?t|do not|won'?t|will not|can'?t|cannot)\s+(want\s+to\s+)?pay\b",
    r"\bfree\s+(tier|only|of\s+charge)\b",
    r"\bfor\s+free\b",
    r"\bno\s+(budget|cost|subscription|cloud|server|hosting|internet|login|account|tracking|telemetry)\b",
    r"\bwithout\s+(paying|a\s+server|internet|the\s+internet|an?\s+account|cloud)\b",
    # "budget" alone is not a limit ("a budget tracker" is a feature). It counts
    # when it is described as tight, fixed, or something to stay within.
    r"\b(tight|small|limited|low|zero|fixed|strict|no|hard)\s+budget\b",
    r"\bbudget\s+(is|of|limit|cap|constraint|under)\b",
    r"\b(on|within|under)\s+(a\s+|my\s+|our\s+)?(tight\s+|small\s+|limited\s+)?budget\b",
    r"\boffline\b",
    r"\b(runs?|stays?|kept|stored?|works?)\s+(only\s+)?(locally|on\s+my\s+(own\s+)?(laptop|machine|computer|device))\b",
    r"\blocal[- ](only|first)\b",
    r"\bself[- ]?host(ed|ing)?\b",
    r"\b(never|not|must\s+not|should\s+not|cannot|can'?t)\s+leave(s)?\b",
    r"\bmust\s+not\b",
    r"\bmust\s+never\b",
    r"\b(only|just)\s+open[- ]source\b",
    r"\bopen[- ]source\s+only\b",
    r"\b(gdpr|hipaa)\b",
    # "private" and "privacy" alone are not limits ("sharing private photos"
    # is a feature). They count when they say how the data must be treated.
    r"\b(keep|keeps|kept|stay|stays|remain|remains)\s+(it\s+|them\s+|everything\s+|all\s+)?private\b",
    r"\b(must|should|has\s+to|needs?\s+to)\s+(be\s+)?(fully\s+|completely\s+)?private\b",
    r"\bprivate\s+by\s+default\b",
    r"\bprivacy[- ](first|focused|preserving|friendly)\b",
    r"\b(strict|strong|high)\s+privacy\b",
    r"\bprivacy\s+(is|matters|requirements?)\b",
]

_COMPILED = [re.compile(pattern, re.IGNORECASE) for pattern in CONSTRAINT_PATTERNS]


def split_sentences(text: str) -> list[str]:
    """Split text into sentences at . ! ? or line breaks, keeping the words unchanged."""
    pieces = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [piece.strip() for piece in pieces if piece.strip()]


def looks_like_constraint(sentence: str) -> bool:
    return any(pattern.search(sentence) for pattern in _COMPILED)


def find_stated_constraints(user_texts: list[str]) -> list[str]:
    """Every sentence the user wrote that reads like a hard limit, in order, once each."""
    found: list[str] = []
    for text in user_texts:
        for sentence in split_sentences(text):
            if looks_like_constraint(sentence) and sentence not in found:
                found.append(sentence)
    return found
