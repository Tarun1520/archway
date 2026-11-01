"""
Lesson 08: Pydantic (data contracts)
====================================

What you learn here
    Pydantic lets you describe the SHAPE of your data as a class, and then
    checks real data against that description:
      - wrong types and missing fields are rejected with a clear error
      - "we do not know" is stored as None, never as a made-up value
      - a model converts to JSON and back without losing anything

How to run (from the project root)
    backend/.venv/bin/python backend/learning/08_pydantic_contracts.py

Where Archway uses this
    Every record in IMPLEMENTATION_GUIDE.md Section 4 (ProjectBrief,
    RepoEvidence, EligibilityResult, DecisionReceipt ...) is a Pydantic model.
    This lesson is a cut-down RepoEvidence.
"""

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, ValidationError


class RepoEvidence(BaseModel):
    """What we know about one GitHub repository, and what we could not find."""

    # Required fields: there is no default, so they must be provided.
    repo: str
    url: str
    retrieved_at: datetime

    # LEARNING NOTE: `str | None = None` means "text, or unknown".
    #   None is how we say "not retrieved". We never write "MIT" or 0 just to
    #   fill the gap, because an invented value looks exactly like a real one.
    license: str | None = None
    stars: int | None = Field(default=None, ge=0)  # ge=0: cannot be negative
    archived: bool | None = None

    # Literal limits the value to this exact list of words.
    fetch_status: Literal["ok", "partial", "failed"]

    # Names of the fields above that we tried to fetch and could not.
    missing_fields: list[str] = Field(default_factory=list)


if __name__ == "__main__":
    print("1. Valid data becomes an object with real Python types")
    evidence = RepoEvidence(
        repo="example/notes-md",
        url="https://github.com/example/notes-md",
        retrieved_at="2026-10-12T10:00:00Z",  # text in, datetime out
        stars="1200",  # text that looks like a number is converted
        fetch_status="partial",
        missing_fields=["license"],
    )
    print("   stars       :", repr(evidence.stars))
    print("   retrieved_at:", repr(evidence.retrieved_at))
    print("   license     :", repr(evidence.license), "<- unknown stays unknown")

    print("\n2. Invalid data is rejected, with every problem listed")
    try:
        RepoEvidence(
            repo="example/broken",
            url="https://github.com/example/broken",
            retrieved_at=datetime.now(timezone.utc),
            stars=-5,  # breaks ge=0
            fetch_status="maybe",  # not one of the allowed words
        )
    except ValidationError as error:
        for problem in error.errors():
            print(f"   field '{problem['loc'][0]}': {problem['msg']}")

    print("\n3. Round trip: object -> JSON text -> object")
    as_json = evidence.model_dump_json()
    restored = RepoEvidence.model_validate_json(as_json)
    print("   JSON     :", as_json)
    print("   identical:", restored == evidence)

    print("\n4. The model can describe itself (useful for APIs and for LLM output)")
    schema = RepoEvidence.model_json_schema()
    print("   required fields:", schema["required"])
