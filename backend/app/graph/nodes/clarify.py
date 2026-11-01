"""
Node: clarify. Pauses the run to ask the user a few questions.

What this node does
    1. Pauses with `interrupt(...)`, handing the questions to the caller.
    2. When the user replies, it sorts the topics into ANSWERED and SKIPPED.
    3. Answered topics are added to what the user has said, and the run goes
       back to `intake` so the brief is drafted again with the new facts.
    4. Skipped topics become visible ASSUMPTIONS. If nothing was answered
       there is no reason to call the model again, so the run goes straight
       to `confirm_brief`.

The "idea" question is special
    When the first message described no project, the only question is
    "what would you like to build?". There is no brief yet, so there is
    nothing to assume and nothing to confirm: the answer is added to what
    the person said and the run goes back to `intake`. It cannot be skipped
    (the API refuses that, and this node re-asks if it ever got here).

The interrupt rule to remember (LEARNING_GUIDE.md topic 11)
    When the run resumes, this function starts again FROM ITS FIRST LINE and
    `interrupt(...)` returns the user's reply instead of pausing. So nothing
    with a side effect is placed above the interrupt.

Why it returns a Command
    A Command changes the state AND chooses the next node in one return value
    (LEARNING_GUIDE.md topic 14). The Literal[...] in the return type lists
    where this node may send the run.
"""

from typing import Literal

from langgraph.runtime import Runtime
from langgraph.types import Command, interrupt

from app.briefing.builder import add_assumptions
from app.graph import events
from app.graph.context import RunContext
from app.graph.state import WorkflowState
from app.models.brief import ProjectBrief
from app.models.workflow import ClarifyAnswer

NODE = "clarify"


async def clarify(state: WorkflowState, runtime: Runtime[RunContext]) -> Command[Literal["intake", "confirm_brief"]]:
    questions = state["open_questions"]
    asks_for_idea = any(question["topic"] == "idea" for question in questions)

    # The run stops here until the user replies. The dictionary is what the
    # UI receives; it must be plain data so it can be saved. Skipping is
    # offered for the architecture questions, never for "what to build".
    reply = interrupt({"node": NODE, "questions": questions, "allow_continue": not asks_for_idea})

    # ---- Everything below runs only after the user has replied --------------
    emit = runtime.stream_writer
    answer = ClarifyAnswer.model_validate(reply)

    asked = [question["topic"] for question in questions]
    answered = {topic: text.strip() for topic, text in answer.answers.items() if topic in asked and text.strip()}
    skipped = [topic for topic in asked if topic not in answered]
    architecture_asked = [question for question in questions if question["topic"] != "idea"]

    update = {
        "open_questions": [],
        "asked_topics": [question["topic"] for question in architecture_asked],
        "asked_questions": architecture_asked,
        "answered_questions": [
            {"topic": question["topic"], "answer": answered[question["topic"]]}
            for question in architecture_asked if question["topic"] in answered
        ],
        "assumed_topics": [topic for topic in skipped if topic != "idea"],
        # Only architecture questions use up the single clarification round.
        "clarify_rounds": state["clarify_rounds"] + (1 if architecture_asked else 0),
    }

    if answered:
        emit(events.activity(f"You answered {len(answered)} question(s); re-reading with your answers"))
        # The answers join the user's own words, so the stated-constraint
        # detector and the model both see them. The idea is the person's own
        # description, so it is added as written.
        update["user_texts"] = [
            text if topic == "idea" else f"Answer about {topic}: {text}" for topic, text in answered.items()
        ]
        return Command(update=update, goto="intake")

    if asks_for_idea:
        # Nothing to assume about a project that has not been described.
        # Going back to intake asks again (without a model call).
        return Command(update=update, goto="intake")

    # Nothing answered: record the assumptions without another model call.
    brief = add_assumptions(ProjectBrief.model_validate(state["brief"]), skipped)
    emit(events.activity(f"Continuing with {len(skipped)} assumption(s), shown separately in the brief"))
    update["brief"] = brief.model_dump(mode="json")
    return Command(update=update, goto="confirm_brief")
