"""
List the licenses of Archway's own dependencies.

What this script does
    Reads the license each installed package DECLARES about itself (Python
    packages in this venv, JavaScript packages in frontend/node_modules) and
    writes a report to docs/dependency-licenses.md.

How to run (from the project root)
    backend/.venv/bin/python backend/scripts/list_licenses.py

Why it exists
    Phase 1 asks for a "license review of Archway's own dependencies". A tool
    that judges other projects' licenses should know its own.

What it cannot tell you
    It reports what each package's metadata says. It does not read license
    files or give legal advice. Anything it marks "needs a look" should be
    checked by a person.

LEARNING NOTE: this script makes no network requests. Everything it reads is
already on this machine.
"""

import json
import re
from collections import Counter
from datetime import date
from importlib import metadata
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPORT = PROJECT_ROOT / "docs" / "dependency-licenses.md"

# Licenses that allow reuse with few conditions. Matching is done on words
# found in the declared license text.
PERMISSIVE_WORDS = ("mit", "bsd", "apache", "isc", "psf", "python software foundation", "ofl", "0bsd",
                    "unlicense", "cc0", "zlib", "blueoak", "mpl")  # MPL: file-level copyleft, fine for use as a library


# Packages whose own metadata declares no license, but whose license FILE a person has read.
# Used only when the metadata is empty, and shown in the report as "checked by hand", so the
# report never pretends the package declared it. Add a line here only after reading the file.
CHECKED_BY_HAND = {
    "khroma": "MIT",  # a dependency of mermaid; its LICENSE file is MIT (read 2026-10-23); package.json has no license field
}


def is_permissive(license_text: str) -> bool:
    lowered = license_text.lower()
    return any(word in lowered for word in PERMISSIVE_WORDS)


# -----------------------------------------------------------------------------
# Python packages
# -----------------------------------------------------------------------------
def python_license(distribution: metadata.Distribution) -> str:
    """Find the declared license, trying the newest metadata field first."""
    info = distribution.metadata
    expression = info.get("License-Expression")
    if expression:
        return expression
    # Older packages describe the license in "classifiers".
    classifiers = [value.split("::")[-1].strip() for value in info.get_all("Classifier") or []
                   if value.startswith("License ::")]
    if classifiers:
        return "; ".join(sorted(set(classifiers)))
    declared = (info.get("License") or "").strip()
    if declared:
        # Some packages paste the whole license text here. Keep the first line.
        return declared.splitlines()[0][:80]
    return "not declared"


def direct_python_requirements() -> set[str]:
    """Package names listed in the two requirements files."""
    names = set()
    for file in ("requirements.txt", "requirements-dev.txt"):
        for line in (PROJECT_ROOT / "backend" / file).read_text(encoding="utf-8").splitlines():
            line = line.split("#", 1)[0].strip()
            if not line or line.startswith("-r"):
                continue
            names.add(re.split(r"[=<>\[!~ ]", line, maxsplit=1)[0].lower().replace("_", "-"))
    return names


def python_rows() -> tuple[list[tuple[str, str, str]], list[tuple[str, str, str]]]:
    direct_names = direct_python_requirements()
    direct, transitive = [], []
    for distribution in metadata.distributions():
        name = (distribution.metadata["Name"] or "").lower().replace("_", "-")
        if not name:
            continue
        row = (name, distribution.version, python_license(distribution))
        (direct if name in direct_names else transitive).append(row)
    return sorted(set(direct)), sorted(set(transitive))


# -----------------------------------------------------------------------------
# JavaScript packages
# -----------------------------------------------------------------------------
def js_license(package_json: dict) -> str:
    declared = package_json.get("license")
    if isinstance(declared, dict):
        declared = declared.get("type")
    return declared or "not declared"


def js_license_for(name: str, package_json: dict) -> str:
    """The declared license; or, when none is declared, the one a person verified from the license file."""
    declared = js_license(package_json)
    if declared == "not declared" and name in CHECKED_BY_HAND:
        return f"{CHECKED_BY_HAND[name]} (checked by hand: its license file; the package declares none)"
    return declared


def js_rows() -> tuple[list[tuple[str, str, str]], list[tuple[str, str, str]]]:
    frontend = PROJECT_ROOT / "frontend"
    manifest = json.loads((frontend / "package.json").read_text(encoding="utf-8"))
    direct_names = set(manifest.get("dependencies", {})) | set(manifest.get("devDependencies", {}))

    direct, transitive = [], []
    modules = frontend / "node_modules"
    # Packages are either node_modules/name or node_modules/@scope/name.
    for package_file in list(modules.glob("*/package.json")) + list(modules.glob("@*/*/package.json")):
        try:
            data = json.loads(package_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        name = data.get("name")
        if not name:
            continue
        row = (name, str(data.get("version", "?")), js_license_for(name, data))
        (direct if name in direct_names else transitive).append(row)
    return sorted(set(direct)), sorted(set(transitive))


# -----------------------------------------------------------------------------
# The report
# -----------------------------------------------------------------------------
def table(rows: list[tuple[str, str, str]]) -> list[str]:
    lines = ["| Package | Version | Declared license | Note |", "|---|---|---|---|"]
    for name, version, license_text in rows:
        note = "" if is_permissive(license_text) else "**needs a look**"
        lines.append(f"| {name} | {version} | {license_text} | {note} |")
    return lines


def summary(rows: list[tuple[str, str, str]]) -> list[str]:
    counts = Counter(license_text for _, _, license_text in rows)
    lines = ["| Declared license | Packages |", "|---|---|"]
    for license_text, count in counts.most_common():
        lines.append(f"| {license_text} | {count} |")
    return lines


def main() -> None:
    python_direct, python_transitive = python_rows()
    js_direct, js_transitive = js_rows()

    flagged = [
        f"{name} ({license_text})"
        for name, _, license_text in python_direct + python_transitive + js_direct + js_transitive
        if not is_permissive(license_text)
    ]

    lines = [
        "# Dependency licenses",
        "",
        f"Generated on {date.today().isoformat()} by `backend/scripts/list_licenses.py`. Do not edit by hand; run the script again.",
        "",
        "This lists the license each installed package **declares in its own metadata**. "
        "It does not read license files and is not legal advice.",
        "",
        "## Packages that need a look",
        "",
    ]
    lines += [f"- {item}" for item in sorted(set(flagged))] or ["None. Every declared license matched the permissive list."]
    lines += ["", "## Backend: packages we chose (requirements files)", "", *table(python_direct)]
    lines += ["", f"## Backend: packages they pull in ({len(python_transitive)})", "", *summary(python_transitive)]
    lines += ["", "## Frontend: packages we chose (package.json)", "", *table(js_direct)]
    lines += ["", f"## Frontend: packages they pull in ({len(js_transitive)})", "", *summary(js_transitive), ""]

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines), encoding="utf-8")

    print(f"Wrote {REPORT.relative_to(PROJECT_ROOT)}")
    print(f"  backend : {len(python_direct)} chosen, {len(python_transitive)} pulled in")
    print(f"  frontend: {len(js_direct)} chosen, {len(js_transitive)} pulled in")
    print(f"  need a look: {len(set(flagged))}")
    for item in sorted(set(flagged)):
        print("   -", item)


if __name__ == "__main__":
    main()
