"""
Evidence: what was actually retrieved, from where, and when.

What this file does
    RepoEvidence  - what we know about one GitHub repository.
    EvidenceItem  - one quoted piece of source material that a claim rests on.

The rule these models protect
    "A failed fetch never becomes a fabricated summary." Missing data is
    None and is NAMED in `missing_fields`, so the UI can show "not retrieved".

How it plugs in
    Phase 3's research nodes will create these. Everything downstream points
    back at evidence through `EvidenceItem.id` (the `evidence_ids` lists).
"""

from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator

from app.models.common import ArchwayModel, ServiceMode

FetchStatus = Literal["ok", "partial", "failed"]
SourceType = Literal["repo_metadata", "readme", "linked_doc", "user_url", "package_registry"]


class RepoEvidence(ArchwayModel):
    repo: str = Field(min_length=1)  # "owner/name"
    url: str = Field(min_length=1)
    retrieved_at: datetime  # when it was FIRST fetched (kept even when cached)

    # Everything below may be unknown. None means "not retrieved".
    description: str | None = None
    language: str | None = None
    topics: list[str] | None = None
    license: str | None = None
    archived: bool | None = None
    last_push: datetime | None = None
    stars: int | None = Field(default=None, ge=0)
    readme_excerpt: str | None = None
    content_hash: str | None = None

    fetch_status: FetchStatus
    # Names of the optional fields above that we tried to get and could not.
    missing_fields: list[str] = Field(default_factory=list)

    # --- Provenance (added in Phase 3) -------------------------------------------
    # Where the data came from: the real GitHub API, or recorded fixture data.
    mode: ServiceMode = "live"
    # True when this was served from the local cache. `retrieved_at` is then
    # the date of the ORIGINAL fetch, never "now".
    from_cache: bool = False
    homepage: str | None = None  # the repository's own link to its docs, if it has one
    # The EvidenceItem ids this repository's facts rest on.
    evidence_ids: list[str] = Field(default_factory=list)
    # Why something is missing, in plain words ("GitHub rate limit reached").
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def missing_fields_are_real_and_failures_stay_empty(self):
        optional = {
            "description", "language", "topics", "license", "archived",
            "last_push", "stars", "readme_excerpt", "content_hash",
        }
        unknown = [name for name in self.missing_fields if name not in optional]
        if unknown:
            raise ValueError(f"missing_fields has names that are not fields: {unknown}")

        # A field cannot be both "missing" and filled in.
        contradictions = [name for name in self.missing_fields if getattr(self, name) is not None]
        if contradictions:
            raise ValueError(f"fields listed as missing but given a value: {contradictions}")

        if self.fetch_status == "failed" and self.readme_excerpt is not None:
            raise ValueError("a failed fetch cannot carry a readme_excerpt")
        return self


class EvidenceItem(ArchwayModel):
    id: str = Field(min_length=1)
    url: str = Field(min_length=1)
    retrieved_at: datetime
    source_type: SourceType

    excerpt: str | None = None  # a SHORT quote, not the whole document
    excerpt_location: str | None = None  # where in the source, e.g. "characters 0-58"
    content_hash: str | None = None

    # The claims this evidence supports (ids are assigned in later phases).
    claim_ids: list[str] = Field(default_factory=list)
    extraction_status: Literal["ok", "partial", "failed"]

    # Phase 3 additions: who produced it, and why it failed (if it did).
    mode: ServiceMode = "live"
    note: str | None = None  # for example "refused: the host resolves to a private address"
    repo: str | None = None  # the repository this belongs to, if any

    @model_validator(mode="after")
    def failed_extraction_has_no_excerpt(self):
        if self.extraction_status == "failed" and self.excerpt is not None:
            raise ValueError("a failed extraction cannot carry an excerpt")
        return self


# --- Reading "license" correctly -------------------------------------------------
#
# A repository's license can be in three different states, and they mean
# different things for the eligibility rules in Phase 4:
#
#   license is a value                       detected  (e.g. "MIT")
#   license is None, "license" NOT missing   none_detected: GitHub looked and found no license file
#   license is None, "license" in missing    not_retrieved: we could not find out
#
# The same idea applies to `readme_excerpt`. This helper names the three states
# in one place so the backend and its tests read them the same way.
def license_state(repo: "RepoEvidence") -> Literal["detected", "none_detected", "not_retrieved"]:
    if repo.license is not None:
        return "detected"
    return "not_retrieved" if "license" in repo.missing_fields else "none_detected"
