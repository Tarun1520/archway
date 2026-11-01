"""
Turning what a tool retrieved into SourceFacts and evidence. Plain Python.

Kept apart from the tools so the rules are in one place and testable:
the license is read the same way whatever the source, and an unknown stays
unknown.
"""

import re

from app.evidence.builders import evidence_id
from app.evidence.extract import doc_excerpt
from app.integrations.npm_client import NpmPackage
from app.integrations.pypi_client import PackageInfo
from app.models.common import ServiceMode
from app.models.evidence import EvidenceItem, RepoEvidence
from app.models.research import Candidate, LicenseStatus, SourceFacts


def license_status_of(license_value: str | None, *, looked_up: bool) -> LicenseStatus:
    if license_value == "NOASSERTION":
        return "unrecognised"
    if license_value:
        return "detected"
    return "none_detected" if looked_up else "not_retrieved"


def facts_from_search_hit(hit: Candidate, mode: ServiceMode) -> tuple[SourceFacts, EvidenceItem]:
    """A search result: facts GitHub reported, not yet inspected."""
    item = EvidenceItem(
        id=evidence_id(hit.url, "repo_metadata"), url=hit.url, retrieved_at=hit.retrieved_at, source_type="repo_metadata",
        excerpt=" · ".join(p for p in [hit.description or "", hit.language or "", f"{hit.stars} stars" if hit.stars is not None else ""] if p),
        excerpt_location="search result fields", extraction_status="ok", mode=mode, repo=hit.repo,
    )
    facts = SourceFacts(
        kind="github", reference=hit.repo, url=hit.url, description=hit.description, license=hit.license,
        # GitHub's search reports a detected license or null, so null is "none detected".
        license_status=license_status_of(hit.license, looked_up=True),
        archived=hit.archived, stars=hit.stars, last_activity=hit.last_push, inspected=False,
        evidence_ids=[item.id], mode=mode,
    )
    return facts, item


def facts_from_inspection(repo: RepoEvidence) -> SourceFacts:
    if repo.license is not None:
        status = license_status_of(repo.license, looked_up=True)
    else:
        status = "not_retrieved" if "license" in repo.missing_fields else "none_detected"
    return SourceFacts(
        kind="github", reference=repo.repo, url=repo.url, description=repo.description, license=repo.license,
        license_status=status, archived=repo.archived, stars=repo.stars, last_activity=repo.last_push,
        inspected=True, evidence_ids=list(repo.evidence_ids), mode=repo.mode,
    )


def _with_description(fields: str, description: str | None) -> str:
    """The registry fields, then the start of the package's own description: what it does, in its own words."""
    if not (description or "").strip():
        return fields
    return f"{fields} · {doc_excerpt(description or '')[0]}"


def facts_from_pypi(package: PackageInfo, mode: ServiceMode) -> tuple[SourceFacts, EvidenceItem]:
    released = package.released.date().isoformat() if package.released else "release date not reported"
    item = EvidenceItem(
        id=evidence_id(package.url, "package_registry"), url=package.url, retrieved_at=package.provenance.retrieved_at,
        source_type="package_registry",
        excerpt=_with_description(
            f"{package.summary or 'no summary'} · version {package.version or '?'} · license {package.license or 'not declared'} · released {released}",
            package.description,
        ),
        excerpt_location="PyPI JSON API fields, then the package description (its opening, and the start of each section when long; badges and markup removed)",
        extraction_status="ok", mode=mode,
    )
    facts = SourceFacts(
        kind="pypi", reference=package.name, url=package.url, description=package.summary, license=package.license,
        license_status=license_status_of(package.license, looked_up=True), last_activity=package.released,
        inspected=True, evidence_ids=[item.id], mode=mode, source_repo=github_repo_of(package.source_url),
    )
    return facts, item


_GITHUB_REPO = re.compile(r"github\.com[/:]([A-Za-z0-9-]+/[A-Za-z0-9_.-]+?)(?:\.git)?(?:[/#?].*)?$", re.I)


def github_repo_of(url: str | None) -> str | None:
    """'owner/name' from a GitHub address in any common form, or None."""
    match = _GITHUB_REPO.search(url or "")
    return match.group(1) if match else None


def facts_from_npm(package: NpmPackage, mode: ServiceMode) -> tuple[SourceFacts, EvidenceItem]:
    item = EvidenceItem(
        id=evidence_id(package.url, "package_registry"), url=package.url, retrieved_at=package.provenance.retrieved_at,
        source_type="package_registry",
        excerpt=f"{package.description or 'no description'} · version {package.version or '?'} · license {package.license or 'not declared'}",
        excerpt_location="npm registry fields", extraction_status="ok", mode=mode,
    )
    facts = SourceFacts(
        kind="npm", reference=package.name, url=package.url, description=package.description, license=package.license,
        license_status=license_status_of(package.license, looked_up=True), inspected=True,
        evidence_ids=[item.id], mode=mode, source_repo=github_repo_of(package.repository),
    )
    return facts, item


def facts_summary(facts: SourceFacts) -> dict:
    """The facts as the model sees them: short, and saying plainly what is unknown."""
    return {
        "source": facts.kind, "reference": facts.reference, "url": facts.url,
        "license": facts.license or {"none_detected": "none detected", "not_retrieved": "not retrieved"}.get(facts.license_status),
        "archived": facts.archived, "stars": facts.stars, "downloads_last_month": facts.downloads_last_month,
        "last_activity": facts.last_activity.date().isoformat() if facts.last_activity else None,
        "inspected": facts.inspected,
    }
