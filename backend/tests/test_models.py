"""
Tests for the data contracts in app/models/.

Checkpoint 1 items covered here:
    - "A sample brief round-trips through the models with no model calls"
    - "Unknown values remain unknown"
"""

import json
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.models.brief import ProjectBrief, Requirement
from app.models.eligibility import EligibilityResult
from app.models.evidence import EvidenceItem, RepoEvidence
from app.models.option import ArchitectureOption, Component, ReusedRepo
from app.models.prompt_pack import Prompt, PromptPack
from app.models.receipt import DecisionReceipt
from app.models.roadmap import RoadmapTask
from app.models.usage import UsageEvent
from app.samples.briefs import BRIEFS_FOLDER, load_sample_briefs

NOW = datetime(2026, 10, 13, 12, 0, tzinfo=timezone.utc)


# --- Sample briefs ----------------------------------------------------------------
def test_there_are_six_to_eight_sample_briefs_all_labelled_demo():
    samples = load_sample_briefs()
    assert 6 <= len(samples) <= 8
    assert all(sample.demo is True for sample in samples)


@pytest.mark.parametrize("sample", load_sample_briefs(), ids=lambda sample: sample.slug)
def test_sample_brief_round_trips_without_losing_anything(sample):
    """object -> JSON text -> object must give back an identical brief."""
    as_json = sample.brief.model_dump_json()
    restored = ProjectBrief.model_validate_json(as_json)
    assert restored == sample.brief


@pytest.mark.parametrize("file", sorted(BRIEFS_FOLDER.glob("*.json")), ids=lambda file: file.stem)
def test_sample_file_on_disk_matches_what_the_model_writes(file):
    """The stored JSON and the model's own output contain the same data."""
    on_disk = json.loads(file.read_text(encoding="utf-8"))["brief"]
    through_model = json.loads(ProjectBrief.model_validate(on_disk).model_dump_json())
    assert through_model == on_disk


# --- Unknown stays unknown --------------------------------------------------------
def test_unknown_brief_values_stay_none_through_a_round_trip():
    brief = ProjectBrief(id="b1", version=1, problem="Something")
    assert brief.users is None
    assert brief.constraints.budget is None

    restored = ProjectBrief.model_validate_json(brief.model_dump_json())
    assert restored.users is None
    assert restored.constraints.budget is None
    assert restored.constraints.privacy is None
    # The JSON itself says null. It does not say "" or "none" or 0.
    assert json.loads(brief.model_dump_json())["users"] is None


def test_unknown_repo_values_stay_none_and_are_named_as_missing():
    evidence = RepoEvidence(
        repo="example/md-vault",
        url="https://github.com/example/md-vault",
        retrieved_at=NOW,
        fetch_status="partial",
        missing_fields=["license", "stars"],
    )
    restored = RepoEvidence.model_validate_json(evidence.model_dump_json())
    assert restored.license is None
    assert restored.stars is None
    assert restored.archived is None  # not retrieved is NOT the same as False
    assert restored.missing_fields == ["license", "stars"]


def test_a_field_cannot_be_both_missing_and_filled_in():
    with pytest.raises(ValidationError):
        RepoEvidence(
            repo="a/b", url="https://github.com/a/b", retrieved_at=NOW,
            fetch_status="partial", license="MIT", missing_fields=["license"],
        )


def test_a_failed_fetch_cannot_carry_a_summary():
    with pytest.raises(ValidationError):
        RepoEvidence(
            repo="a/b", url="https://github.com/a/b", retrieved_at=NOW,
            fetch_status="failed", readme_excerpt="An invented summary",
        )
    with pytest.raises(ValidationError):
        EvidenceItem(
            id="e1", url="https://example.test", retrieved_at=NOW, source_type="readme",
            extraction_status="failed", excerpt="An invented quote",
        )


# --- Contract rules ---------------------------------------------------------------
def test_unknown_field_names_are_rejected_not_ignored():
    with pytest.raises(ValidationError):
        ProjectBrief(id="b1", version=1, problem="x", licence_typo="MIT")


def test_requirement_ids_must_be_unique():
    with pytest.raises(ValidationError):
        ProjectBrief(
            id="b1", version=1, problem="x",
            must_have=[Requirement(id="REQ-1", text="a"), Requirement(id="REQ-1", text="b")],
        )


def test_conflict_must_point_at_real_requirements():
    with pytest.raises(ValidationError):
        ProjectBrief(
            id="b1", version=1, problem="x",
            conflicts=[{"description": "clash", "requirement_ids": ["REQ-99"]}],
        )


def test_non_eligible_status_needs_a_reason():
    with pytest.raises(ValidationError):
        EligibilityResult(repo="a/b", status="excluded", policy_version="1")
    assert EligibilityResult(repo="a/b", status="eligible", policy_version="1").reasons == []


def test_reuse_component_must_name_its_repository():
    with pytest.raises(ValidationError):
        Component(name="Search", responsibility="Index notes", kind="reuse")
    with pytest.raises(ValidationError):
        ArchitectureOption(
            id="o1", version=1, brief_version=1, summary="s",
            components=[Component(name="Search", responsibility="Index", kind="reuse", repo="a/b")],
            reused_repos=[],  # a/b is used above but not listed here
        )
    option = ArchitectureOption(
        id="o1", version=1, brief_version=1, summary="s",
        components=[Component(name="Search", responsibility="Index", kind="reuse", repo="a/b")],
        reused_repos=[ReusedRepo(repo="a/b", role="search engine")],
    )
    assert option.approved is False


def test_prompt_must_point_at_a_task_in_the_same_pack():
    task = RoadmapTask(id="T-1", goal="Scaffold", scope="Create the folders")
    with pytest.raises(ValidationError):
        PromptPack(
            id="p1", architecture_version=1, tasks=[task], generated_at=NOW,
            review_notice="Generated code requires human review.",
            prompts=[Prompt(id="01", title="Scaffold", task_ids=["T-404"], body="...")],
        )


def test_receipt_keeps_absent_confidence_as_none_and_always_records_the_mode():
    receipt = DecisionReceipt(
        id="r1", created_at=NOW, candidate_id="a/b", question_type="requirement_fit",
        rubric_version="1", jev_mode="fixture", needs_review=True,
    )
    restored = DecisionReceipt.model_validate_json(receipt.model_dump_json())
    assert restored.reported_confidence is None  # absent is not 0.5
    assert restored.final_result is None  # "not evaluated", not a neutral guess
    assert restored.jev_mode == "fixture"
    with pytest.raises(ValidationError):  # the mode can never be left out
        DecisionReceipt(
            id="r2", created_at=NOW, candidate_id="a/b", question_type="requirement_fit",
            rubric_version="1", needs_review=False,
        )


def test_usage_event_counts_must_be_positive():
    with pytest.raises(ValidationError):
        UsageEvent(run_id="r", service="llm", mode="fixture", count=0, timestamp=NOW)
