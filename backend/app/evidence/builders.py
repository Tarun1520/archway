"""
Building RepoEvidence and EvidenceItem records from what was fetched.

What this file does
    Pure functions: fetched facts in, honest records out. No network, no
    database, so every rule here is tested exactly.

The rules it keeps
    - A field that could not be fetched is None AND listed in
      `missing_fields`. It is never filled with a guess.
    - "GitHub says there is no README" and "we could not fetch the README"
      are different. The first is a fact (the README is None and is not
      listed as missing); the second is `not retrieved` (listed as missing).
    - A failed fetch carries no excerpt, ever.
    - `retrieved_at` is the date of the ORIGINAL fetch, even for cached data.
      A record built from several answers carries the OLDEST date, because
      the whole record is only as fresh as its oldest part.

How it plugs in
    app/graph/nodes/inspect_repos.py and fetch_docs.py call these.
"""

import hashlib
import json
from datetime import datetime

from app.models.common import ServiceMode
from app.models.evidence import EvidenceItem, RepoEvidence
from app.models.research import Candidate
from app.evidence.extract import EXCERPT_LENGTH, doc_excerpt, html_to_text, make_excerpt, sha256_of, tidy_text
from app.integrations.github_client import LicenseOutcome, ReadmeOutcome
from app.integrations.safe_fetch import FetchedPage, FetchRefused


def evidence_id(url: str, source_type: str) -> str:
    """A stable id: the same source always gets the same id."""
    return "ev-" + hashlib.sha1(f"{source_type}|{url}".encode("utf-8")).hexdigest()[:12]


def _metadata_excerpt(candidate: Candidate) -> str:
    parts = []
    if candidate.language:
        parts.append(candidate.language)
    if candidate.stars is not None:
        parts.append(f"{candidate.stars} stars")
    if candidate.last_push:
        parts.append(f"last push {candidate.last_push.date().isoformat()}")
    parts.append("archived" if candidate.archived else "not archived" if candidate.archived is False else "archive status unknown")
    if candidate.topics:
        parts.append("topics: " + ", ".join(candidate.topics[:6]))
    return " · ".join(parts)


def build_repo_evidence(
    candidate: Candidate,
    *,
    readme: ReadmeOutcome | None,
    readme_error: str | None,
    license_: LicenseOutcome | None,
    license_error: str | None,
    mode: ServiceMode,
) -> tuple[RepoEvidence, list[EvidenceItem]]:
    notes: list[str] = []
    missing: list[str] = []
    items: list[EvidenceItem] = []
    retrieved = [candidate.retrieved_at]
    from_cache = candidate.from_cache

    # --- License ------------------------------------------------------------------
    license_value: str | None = None
    if license_ is not None:
        retrieved.append(license_.provenance.retrieved_at)
        from_cache = from_cache or license_.provenance.from_cache
        license_value = license_.spdx_id if license_.found else None  # None: no license detected
    else:
        # The license request failed. The search result's license is GitHub's
        # own answer to the same question, so use it if it has a value.
        if candidate.license is not None:
            license_value = candidate.license
            notes.append(f"license taken from the search result ({license_error})")
        else:
            missing.append("license")
            notes.append(f"license not retrieved ({license_error})")

    # --- README -------------------------------------------------------------------
    readme_excerpt: str | None = None
    content_hash: str | None = None
    readme_item: EvidenceItem | None = None
    readme_url = f"{candidate.url}#readme"
    if readme is not None:
        retrieved.append(readme.provenance.retrieved_at)
        from_cache = from_cache or readme.provenance.from_cache
        if readme.found and readme.text is not None:
            # The README cleaned of badges and markup: its opening, and the start of each section when it is long.
            readme_excerpt, location = doc_excerpt(readme.text)
            location += " of the README, with badges and markup removed"
            content_hash = sha256_of(readme.text)
            if readme.truncated:
                notes.append("README is very long: only the first part was kept")
            readme_item = EvidenceItem(
                id=evidence_id(readme_url, "readme"), url=readme_url, retrieved_at=readme.provenance.retrieved_at,
                source_type="readme", excerpt=readme_excerpt, excerpt_location=location, content_hash=content_hash,
                extraction_status="partial" if readme.truncated else "ok", mode=mode, repo=candidate.repo,
            )
        else:
            notes.append("GitHub reports no README for this repository")
    else:
        missing += ["readme_excerpt", "content_hash"]
        notes.append(f"README not retrieved ({readme_error})")
        readme_item = EvidenceItem(
            id=evidence_id(readme_url, "readme"), url=readme_url, retrieved_at=min(retrieved),
            source_type="readme", extraction_status="failed", mode=mode, repo=candidate.repo,
            note=f"not retrieved: {readme_error}",
        )

    # --- Status ---------------------------------------------------------------------
    failures = (license_ is None) + (readme is None)
    status = "ok" if failures == 0 else "failed" if failures == 2 else "partial"
    oldest = min(retrieved)

    # --- The metadata evidence item ---------------------------------------------------
    metadata_text = _metadata_excerpt(candidate)
    metadata_url = candidate.url
    metadata_item = EvidenceItem(
        id=evidence_id(metadata_url, "repo_metadata"), url=metadata_url, retrieved_at=candidate.retrieved_at,
        source_type="repo_metadata", excerpt=metadata_text, excerpt_location="search result fields",
        content_hash=sha256_of(json.dumps(candidate.model_dump(mode="json", exclude={"found_by", "retrieved_at", "from_cache"}),
                                          sort_keys=True)),
        extraction_status="ok", mode=mode, repo=candidate.repo,
    )
    items.append(metadata_item)
    if readme_item is not None:
        items.append(readme_item)

    repo = RepoEvidence(
        repo=candidate.repo, url=candidate.url, retrieved_at=oldest,
        description=candidate.description, language=candidate.language, topics=candidate.topics,
        license=license_value, archived=candidate.archived, last_push=candidate.last_push, stars=candidate.stars,
        readme_excerpt=readme_excerpt, content_hash=content_hash,
        fetch_status=status, missing_fields=missing, mode=mode, from_cache=from_cache,
        homepage=candidate.homepage, evidence_ids=[item.id for item in items], notes=notes,
    )
    return repo, items


def build_doc_item(
    url: str,
    source_type: str,
    *,
    page: FetchedPage | None,
    refused: FetchRefused | None,
    retrieved_at: datetime,
    mode: ServiceMode,
    repo: str | None = None,
) -> EvidenceItem:
    """One evidence item for a documentation page, fetched or refused."""
    if page is None:
        reason = refused.message if refused else "not retrieved"
        return EvidenceItem(
            id=evidence_id(url, source_type), url=url, retrieved_at=retrieved_at, source_type=source_type,
            extraction_status="failed", mode=mode, repo=repo, note=reason,
        )
    is_html = page.content_type.lower().startswith(("text/html", "application/xhtml"))
    text = html_to_text(page.text) if is_html else tidy_text(page.text)
    excerpt, location = make_excerpt(text, length=EXCERPT_LENGTH)
    return EvidenceItem(
        id=evidence_id(url, source_type), url=page.url, retrieved_at=page.retrieved_at, source_type=source_type,
        excerpt=excerpt or None, excerpt_location=location if excerpt else None,
        content_hash=sha256_of(page.text),
        extraction_status="partial" if page.truncated or not excerpt else "ok",
        mode=mode, repo=repo,
        note=("the page was longer than the size limit; only the start was read" if page.truncated else
              (f"redirected via {len(page.redirects)} hop(s)" if page.redirects else None)),
    )
