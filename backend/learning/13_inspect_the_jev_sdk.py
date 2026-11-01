"""
Lesson 13: Inspect an SDK before you code against it (Jev / TypeSafe)
=====================================================================

What you learn here
    A habit, more than a library: before writing code that calls an SDK,
    ask the INSTALLED package what it really offers. Field names you "sort of
    remember" are the most common source of bugs with any new SDK.

    This script makes NO network call and needs NO API key. It only reads the
    package that pip installed, and builds one question object locally.

How to run (from the project root)
    backend/.venv/bin/python backend/learning/13_inspect_the_jev_sdk.py

Where Archway uses this
    IMPLEMENTATION_GUIDE.md Section 6.4 says "Verify the official SDK first".
    This is how. backend/app/jev/ will be written from what this prints, and
    the live behaviour still has to be confirmed in the Phase 4 spike.
"""

import inspect
from importlib.metadata import version

import typesafe_sdk
from typesafe_sdk import Choice, Score, TypeSafeClient


def show_fields(model_class) -> None:
    """Print the fields of a Pydantic model class (see Lesson 08)."""
    print(f"  {model_class.__name__}")
    for name, field in model_class.model_fields.items():
        required = "required" if field.is_required() else "optional"
        print(f"      {name:14} {required}")


if __name__ == "__main__":
    print("Installed version: typesafe-sdk", version("typesafe-sdk"))

    print("\n1. How is the client created? (constructor arguments)")
    for name in inspect.signature(TypeSafeClient.__init__).parameters:
        if name != "self":
            print("     ", name)

    print("\n2. What does a request need? (arguments of client.system_one)")
    for name in inspect.signature(TypeSafeClient.system_one).parameters:
        if name != "self":
            print("     ", name)

    print("\n3. What can we ASK? (question types and their fields)")
    for question_type in (typesafe_sdk.Choice, typesafe_sdk.Score, typesafe_sdk.Noul):
        show_fields(question_type)

    print("\n4. What comes BACK? (answer types and their fields)")
    for answer_type in (
        typesafe_sdk.SystemOneResponse,
        typesafe_sdk.ChoiceAnswer,
        typesafe_sdk.ScoreAnswer,
        typesafe_sdk.NoulAnswer,
        typesafe_sdk.Usage,
    ):
        show_fields(answer_type)

    print("\n5. Which errors can it raise? (so we can handle 'Jev unavailable')")
    for name in dir(typesafe_sdk):
        if name.endswith("Error"):
            print("     ", name)

    # LEARNING NOTE: building a question is local work, with no network.
    #   The question types are Pydantic models, so the SDK checks our question
    #   the moment we create it. The WORDING below is only an illustration of
    #   Archway's decisions, not a tested rubric. In particular, how Jev reads
    #   a Score's `criteria` list (we assume: ordered levels, lowest first) is
    #   an assumption to confirm in the official docs before relying on it.
    print("\n6. Building question objects locally (nothing is sent)")
    fit_question = Choice(
        instructions="Does the repository described in the state satisfy this requirement: offline use?",
        criteria={
            "satisfies": "The evidence explicitly shows the requirement is met.",
            "does_not_satisfy": "The evidence shows the requirement is not met.",
            "cannot_tell": "The evidence does not say either way.",
        },
    )
    print("  ", fit_question.model_dump())

    risk_question = Score(
        instructions="How risky is integrating this repository for the brief in the state?",
        criteria=["very low risk", "low risk", "moderate risk", "high risk", "very high risk"],
    )
    print("  ", risk_question.model_dump())
