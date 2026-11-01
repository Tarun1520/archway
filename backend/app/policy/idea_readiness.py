"""
Is there enough to draft a brief? Decided in plain Python, before any model call.

What this file does
    `idea_readiness(user_texts)` answers: has the person described something
    specific enough to start? It returns `ready` and, when not ready, a short
    `reason` written for the person ("Say what you want to build...").

The rule
    1. Greetings and filler never count (app/policy/small_talk.py).
    2. The description needs SPECIFIC words: words that say what this thing
       is or does. Generic words ("app", "build", "something", "want",
       "website") say nothing about the project, so "build an app" is not
       enough, while "a todo app" or "CLI to rename photos" is.
       Ready when there are at least two specific words, or one specific word
       in a description of three words or more.

Why plain code
    The button that starts the brief asks this every time a message is saved.
    A model call for that would cost money and time; a word rule is instant
    and always gives the same answer. The model still has the last word later:
    if it finds no project in the text, it asks "What would you like to
    build?" (app/graph/nodes/intake.py).

How it plugs in
    - GET /api/projects/{id}/readiness (app/api/readiness.py): the studio
      locks "Create brief" and shows the reason.
    - WorkflowService.start refuses to start a run that is not ready.
"""

import re
from dataclasses import dataclass

from app.policy.small_talk import is_small_talk

# Words that say nothing about WHAT is being built: kinds of thing, wishes,
# fillers and the most common short words. Only these are ignored; every
# other word of three letters or more counts as specific.
GENERIC_WORDS = frozenset("""
    app apps application applications website websites site sites web tool tools system systems platform
    software program programs project projects product products thing things something anything stuff idea ideas
    build building make making create creating develop developing design want wants wanted need needs would could
    should will can like love please help start begin new simple good great cool nice best basic easy
    the and for with that this these those you your our ours mine have has had just some any also very really
    hello hey there thanks thank test testing okay yes not but are was were been being let lets about
    how what why who whom whose where when which does did doing done going goes today tomorrow tonight tell told know
    think thought mean means maybe still already ever never always into over then than them they their here more
    most much many fine well sorry great doing feel feeling feels hope wondering curious question questions
    work works working
    """.split())

MIN_SPECIFIC = 2
MIN_WORDS_WITH_ONE_SPECIFIC = 3
_ANSWER_PREFIX = "Answer about "
_WORD = re.compile(r"[^\W\d_][\w'-]*", re.UNICODE)

NOT_DESCRIBED = "Say what you want to build: what it should do, and who it is for. One clear sentence is enough."
TOO_VAGUE = "Add a little more detail: what should it do, or what is it for? A name like “an app” is not enough to draft a brief."


@dataclass(frozen=True)
class Readiness:
    ready: bool
    reason: str | None


def idea_readiness(user_texts: list[str]) -> Readiness:
    """Whether the person's own words (not answers to questions) are enough to draft a brief."""
    idea_texts = [text for text in user_texts if not text.startswith(_ANSWER_PREFIX)]
    meaningful = [text for text in idea_texts if not is_small_talk(text)]
    if not meaningful:
        return Readiness(False, NOT_DESCRIBED)

    words = [word.lower() for text in meaningful for word in _WORD.findall(text)]
    specific = {word for word in words if len(word) >= 3 and word not in GENERIC_WORDS}
    if len(specific) >= MIN_SPECIFIC or (specific and len(words) >= MIN_WORDS_WITH_ONE_SPECIFIC):
        return Readiness(True, None)
    return Readiness(False, TOO_VAGUE)
