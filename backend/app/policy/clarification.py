"""
Deciding which questions are worth asking the user.

The policy (IMPLEMENTATION_GUIDE.md, Phase 2)
    Ask ONLY questions whose answer changes the architecture:
        deployment     local or hosted?
        users          one person or several?
        sensitive_data personal or confidential data?
        integrations   a service it MUST connect to?
        budget         a hard spending limit?
    Ask each topic at most once, ask at most MAX_QUESTIONS at a time, and
    always let the user skip with "Continue with assumptions".

Two rules added after a real bug
    The old version asked the same fixed questions for ANY input, even "hi".
      1. NOTHING TO ASK ABOUT YET. If the text does not describe a project,
         no architecture question is asked. The only question is the "idea"
         question: what would you like to build?
      2. QUESTIONS BELONG TO THE PROJECT. The model suggests the question
         wording, written about THIS project, and only for facts that are
         still unknown. This file keeps the model on a leash: the topic must
         be one of the five, still unknown, not asked before, at most
         MAX_QUESTIONS in total, in a fixed priority order. If the model
         suggests nothing for a topic, that topic is not asked.

Two OPEN topics, added after a review of a real run (docs/reviews/2026-10-19-argon-review-assessment.md)
    The five topics above are facts about the design. They cannot ask "what do you mean by X?", so a run whose
    central term the model did not know went ahead on a guess, and a message that pointed at "the two links"
    (never pasted) was never asked for them. So:
        meaning   what a term central to the idea means, when it is undefined and the readings lead to
                  different designs
        material  something the person refers to but did not include (links, files, a document)
    They come FIRST (a design built on a misread term is wrong everywhere), have no stock wording (the model must
    write the question about the actual term), and are asked only when the model raises them.

Why the leash is plain Python
    Left to itself a model tends to ask many questions. Code bounds the
    number and the topics; the model only supplies relevance and wording.

How it plugs in
    app/graph/nodes/intake.py calls `has_project` and `questions_for` after
    the model drafts a brief. app/graph/nodes/clarify.py uses
    `ASSUMPTION_IF_SKIPPED` when the user continues without answering.
"""

from app.models.brief_draft import BriefDraft
from app.models.workflow import ClarifyQuestion

MAX_QUESTIONS = 3
MAX_QUESTION_LENGTH = 220

# The order is the priority: if more than MAX_QUESTIONS topics qualify, the
# ones nearest the top are asked.
TOPIC_ORDER = ["deployment", "users", "sensitive_data", "budget", "integrations"]
# Asked before the fact topics, and only when the model raises them with its own wording.
OPEN_TOPICS = ["meaning", "material"]

# Used only when the model suggests a topic but gives no usable wording, and by
# the fixture model (which has no way to write project-specific questions).
QUESTION_TEXT = {
    "deployment": "Where should this run: only on your own machine, or on a server other people can reach?",
    "users": "Is this for one person, or will several people use it together?",
    "sensitive_data": "Will it handle personal, confidential or otherwise sensitive data?",
    "budget": "Is there a hard limit on cost, such as no paid services at all?",
    "integrations": "Is there any outside service or tool it must connect to?",
}

# Shown as "Why we ask" when the model gave no usable reason.
WHY_TEXT = {
    "deployment": "Running on one machine needs no server; a service other people reach needs one running all the time.",
    "users": "One person needs no accounts or sharing; several people need accounts, permissions and shared data.",
    "sensitive_data": "Sensitive data limits where it can be stored and which outside services may see it.",
    "budget": "A hard cost limit rules out paid hosting and paid services.",
    "integrations": "A required outside service becomes part of the design; none keeps it self-contained.",
    "meaning": "The design depends on what this term means; a guess would send the research in the wrong direction.",
    "material": "You mentioned it but it was not included, and it may decide what should be built.",
}

# The one question asked when nothing has been described yet.
IDEA_QUESTION = ClarifyQuestion(
    topic="idea",
    question="What would you like to build? Describe it in a sentence or two: what it should do and who it is for.",
)

# What Archway assumes for a topic the user chose not to answer. Each of these
# is shown to the user as an ASSUMPTION, clearly apart from what they said.
ASSUMPTION_IF_SKIPPED = {
    "deployment": "It runs locally on one machine.",
    "users": "It is used by one person, with no accounts or sharing.",
    "sensitive_data": "It does not handle sensitive personal data.",
    "budget": "No paid services are used.",
    "integrations": "It does not have to connect to any particular outside service.",
    "meaning": "Archway went ahead with its own reading of the term it asked about (see the other assumptions).",
    "material": "Archway went ahead without the material you mentioned.",
}

SKIPPED_REASON = "You chose to continue without answering this question."


def has_project(draft: BriefDraft) -> bool:
    """True when the draft describes something to build.

    Both must hold: the model said so, AND it produced a problem statement.
    A model that says "yes" but wrote nothing is treated as "no".
    """
    return draft.describes_project and bool((draft.problem or "").strip())


def unknown_topics(draft: BriefDraft) -> list[str]:
    """The architecture-changing topics the model could not find in the user's text."""
    is_unknown = {
        "deployment": draft.deployment is None,
        "users": draft.multi_user is None,
        "sensitive_data": draft.handles_sensitive_data is None,
        "budget": draft.budget is None,
        "integrations": draft.mandatory_integrations is None,
    }
    return [topic for topic in TOPIC_ORDER if is_unknown[topic]]


def _clean_question(text: str) -> str:
    """Tidy the model's wording, or return "" if it is not usable."""
    cleaned = " ".join(text.split())
    if not cleaned or len(cleaned) > MAX_QUESTION_LENGTH:
        return ""
    return cleaned if cleaned.endswith("?") else cleaned.rstrip(".!") + "?"


def _clean_reason(text: str) -> str:
    cleaned = " ".join(text.split())
    return cleaned if 0 < len(cleaned) <= MAX_QUESTION_LENGTH else ""


def questions_for(draft: BriefDraft, already_asked: list[str]) -> list[ClarifyQuestion]:
    """The questions to ask now. An empty list means "no need to ask anything"."""
    if not has_project(draft):
        return []  # nothing described: the caller asks the idea question instead

    unknown = set(unknown_topics(draft)) | set(OPEN_TOPICS)  # an open topic is "unknown" whenever the model raises it
    suggested: dict[str, ClarifyQuestion] = {}
    for item in draft.clarifying_questions:
        if item.topic in unknown and item.topic not in already_asked and item.topic not in suggested:
            question = _clean_question(item.question)
            if not question and item.topic in OPEN_TOPICS:
                continue  # no stock wording exists for these: a question about nothing in particular is not asked
            suggested[item.topic] = ClarifyQuestion(
                topic=item.topic,
                question=question or QUESTION_TEXT[item.topic],
                why=_clean_reason(item.why_it_matters) or WHY_TEXT[item.topic],
            )

    return [suggested[topic] for topic in [*OPEN_TOPICS, *TOPIC_ORDER] if topic in suggested][:MAX_QUESTIONS]
