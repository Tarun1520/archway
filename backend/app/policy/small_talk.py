"""
Telling "hi" apart from a project idea, without asking a model.

What this file does
    Answers one question in plain Python: "has the person described anything
    to build yet, or only said hello?"

Why it exists
    A model reading "hi" finds nothing, and the old rules then asked the same
    architecture questions about nothing. This check runs BEFORE the model is
    called, so a greeting costs no model call and gets one sensible reply:
    "What would you like to build?".

Its honest limit
    It recognises short greetings and filler, not every kind of non-idea. The
    model also reports `describes_project`, which catches the rest; this check
    is the cheap first line.

How it plugs in
    app/graph/nodes/intake.py calls `only_small_talk` before any model call.
"""

import re

# Whole-message patterns: the entire text must be one of these.
_SMALL_TALK = re.compile(
    r"""^\W*(
        h+i+ | hello+ | hey+ | heya | hiya | hola | yo | sup | namaste
        | good\s+(morning|afternoon|evening|night)
        | test(ing)? | ping | ok(ay)? | thanks | thank\s+you | help | start | begin | \?+
    )(\s+(there|archway|everyone|all|again))?\W*$""",
    re.IGNORECASE | re.VERBOSE,
)

# Lines the workflow adds itself (answers to questions). They are not the
# person's description of an idea.
_ANSWER_PREFIX = "Answer about "


def is_small_talk(text: str) -> bool:
    """True for a greeting or filler, or for text with no words in it."""
    stripped = text.strip()
    if not re.search(r"[^\W\d_]{2,}", stripped):  # needs at least two letters in a row
        return True
    return bool(_SMALL_TALK.match(stripped))


def only_small_talk(user_texts: list[str]) -> bool:
    """True when nothing the person wrote describes a project."""
    idea_texts = [text for text in user_texts if not text.startswith(_ANSWER_PREFIX)]
    return all(is_small_talk(text) for text in idea_texts)
