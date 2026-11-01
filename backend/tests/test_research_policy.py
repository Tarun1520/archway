"""
Tests for the plain-Python research rules the agents' tools rely on:
query cleaning, URL finding, and evidence records.

No model, no network. That is why these can be exact.
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.models.evidence import EvidenceItem, RepoEvidence, license_state
from app.models.research import Candidate
from app.tools.github_tools import clean_query
from app.evidence.builders import build_doc_item, build_repo_evidence, evidence_id
from app.integrations.github_client import LicenseOutcome, Provenance, ReadmeOutcome
from app.integrations.safe_fetch import FetchedPage, FetchRefused
from app.evidence.urls import MAX_USER_URLS, find_urls

NOW = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)
EARLIER = NOW - timedelta(days=2)


# --- Query cleaning --------------------------------------------------------------
@pytest.mark.parametrize("text, expected", [
    ("markdown notes offline search", "markdown notes offline search"),
    ("markdown notes language:typescript", "markdown notes language:typescript"),
    ("notes license:mit archived:false stars:>100", "notes"),            # filters that hide results are removed
    ("notes AND search OR sync NOT wiki", "notes search sync wiki"),      # boolean words removed
    ("notes repo:someone/secret user:bob org:acme", "notes"),
    ("notes see https://evil.example/x?q=1 search", "notes see search"),  # addresses are not search words
    ("a b c", ""),                                                        # nothing usable
    ("", ""),
])
def test_queries_keep_keywords_and_a_few_safe_qualifiers(text, expected):
    assert clean_query(text) == expected


def test_a_query_stays_short_and_has_few_keywords():
    query = clean_query(" ".join(f"word{n}" for n in range(40)))
    assert len(query) <= 120 and len(query.split()) <= 6


# --- URLs ----------------------------------------------------------------------------
def test_urls_are_found_cleaned_deduplicated_and_capped():
    texts = [
        "See https://docs.example.org/guide, and (https://other.example.org/a). Also https://docs.example.org/guide.",
        "Answer about budget: https://ignored.example.org/",
        "http://plain.example.org/x https://c.example.org https://d.example.org",
    ]
    urls = find_urls(texts)
    assert urls[:3] == ["https://docs.example.org/guide", "https://other.example.org/a", "http://plain.example.org/x"]
    assert len(urls) == MAX_USER_URLS and "https://ignored.example.org/" not in urls


# --- Evidence records ------------------------------------------------------------------
def candidate(name, stars=0):
    return Candidate(repo=f"o/{name}", url=f"https://github.com/o/{name}", stars=stars, retrieved_at=NOW)


def provenance(when=NOW, cached=False):
    return Provenance(retrieved_at=when, from_cache=cached, requested=not cached)


def test_a_fully_retrieved_repository_is_ok_and_has_a_short_excerpt_and_a_hash():
    repo, items = build_repo_evidence(
        candidate("notes", stars=10).model_copy(update={"license": "MIT"}),
        readme=ReadmeOutcome("# Notes\n" + "word " * 500, True, False, "https://github.com/o/notes#readme", provenance()),
        readme_error=None,
        license_=LicenseOutcome("MIT", "MIT License", True, provenance()), license_error=None, mode="fixture",
    )
    assert repo.fetch_status == "ok" and repo.license == "MIT" and repo.missing_fields == []
    # still an excerpt, never the whole README (2,500 characters in, at most DOC_EXCERPT_LENGTH out)
    assert len(repo.readme_excerpt) <= 1500 and repo.readme_excerpt.startswith("Notes word") and len(repo.content_hash) == 64
    assert {item.source_type for item in items} == {"repo_metadata", "readme"}
    assert repo.evidence_ids == [item.id for item in items]
    assert license_state(repo) == "detected"


def test_no_readme_and_no_license_on_github_are_facts_not_missing_data():
    repo, items = build_repo_evidence(
        candidate("bare"),
        readme=ReadmeOutcome(None, False, False, None, provenance()), readme_error=None,
        license_=LicenseOutcome(None, None, False, provenance()), license_error=None, mode="live",
    )
    assert repo.fetch_status == "ok" and repo.missing_fields == []
    assert repo.license is None and repo.readme_excerpt is None
    assert license_state(repo) == "none_detected"
    assert [item.source_type for item in items] == ["repo_metadata"]


def test_a_failed_readme_fetch_is_missing_and_never_has_an_excerpt():
    repo, items = build_repo_evidence(
        candidate("flaky"),
        readme=None, readme_error="GitHub did not answer within 15 seconds (tried 3 times)",
        license_=LicenseOutcome("MIT", "MIT License", True, provenance()), license_error=None, mode="live",
    )
    assert repo.fetch_status == "partial"
    assert repo.readme_excerpt is None and "readme_excerpt" in repo.missing_fields
    failed = next(item for item in items if item.source_type == "readme")
    assert failed.extraction_status == "failed" and failed.excerpt is None and "not retrieved" in failed.note


def test_a_failed_license_fetch_is_not_retrieved_unless_the_search_result_had_one():
    unknown, _ = build_repo_evidence(
        candidate("a"), readme=ReadmeOutcome("x", True, False, None, provenance()), readme_error=None,
        license_=None, license_error="rate limit", mode="live",
    )
    assert unknown.license is None and "license" in unknown.missing_fields and license_state(unknown) == "not_retrieved"

    fallback, _ = build_repo_evidence(
        candidate("b").model_copy(update={"license": "Apache-2.0"}),
        readme=ReadmeOutcome("x", True, False, None, provenance()), readme_error=None,
        license_=None, license_error="rate limit", mode="live",
    )
    assert fallback.license == "Apache-2.0" and "license" not in fallback.missing_fields
    assert any("taken from the search result" in note for note in fallback.notes)


def test_everything_failing_is_a_failed_fetch_with_no_summary():
    repo, _ = build_repo_evidence(
        candidate("down"), readme=None, readme_error="down", license_=None, license_error="down", mode="live"
    )
    assert repo.fetch_status == "failed" and repo.readme_excerpt is None


def test_the_record_carries_the_oldest_retrieval_date_and_notes_cached_data():
    repo, items = build_repo_evidence(
        candidate("mixed"),
        readme=ReadmeOutcome("hello", True, False, None, provenance(EARLIER, cached=True)), readme_error=None,
        license_=LicenseOutcome("MIT", None, True, provenance(NOW)), license_error=None, mode="live",
    )
    assert repo.retrieved_at == EARLIER and repo.from_cache is True
    readme_item = next(item for item in items if item.source_type == "readme")
    assert readme_item.retrieved_at == EARLIER  # the item keeps ITS original date too


def test_evidence_ids_are_stable():
    assert evidence_id("https://x", "readme") == evidence_id("https://x", "readme")
    assert evidence_id("https://x", "readme") != evidence_id("https://x", "linked_doc")


def test_a_refused_page_is_kept_as_failed_evidence_with_the_reason():
    refused = FetchRefused("unsafe", "refused: localhost is a local name")
    item = build_doc_item("https://localhost/x", "user_url", page=None, refused=refused, retrieved_at=NOW, mode="live")
    assert item.extraction_status == "failed" and item.excerpt is None and item.note == refused.message


def test_a_fetched_html_page_becomes_a_short_text_excerpt():
    page = FetchedPage("https://d.example/x", "text/html", "<html><script>bad()</script><body><h1>Guide</h1><p>Hello   there</p></body></html>",
                       False, NOW, ())
    item = build_doc_item("https://d.example/x", "linked_doc", page=page, refused=None, retrieved_at=NOW, mode="live", repo="o/r")
    assert item.excerpt == "Guide Hello there" and "bad()" not in item.excerpt
    assert item.extraction_status == "ok" and item.repo == "o/r" and len(item.content_hash) == 64


def test_models_still_reject_a_failed_record_that_carries_a_summary():
    with pytest.raises(ValueError):
        RepoEvidence(repo="o/r", url="https://github.com/o/r", retrieved_at=NOW, fetch_status="failed", readme_excerpt="x")
    with pytest.raises(ValueError):
        EvidenceItem(id="e", url="https://x", retrieved_at=NOW, source_type="readme", excerpt="x", extraction_status="failed")
