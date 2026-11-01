"""Evidence that can support a claim: documentation text, cleaned, instead of a one-line summary or a badge row."""

from datetime import datetime, timezone

from app.evidence.extract import DOC_EXCERPT_LENGTH, clean_doc_text, doc_excerpt
from app.integrations.github_client import Provenance
from app.integrations.pypi_client import PackageInfo
from app.tools.facts import facts_from_pypi

README = """\
[![Build](https://img.shields.io/badge/build-passing-green.svg)](https://ci.example.test)
![logo](docs/logo.png)
<p align="center"><img src="x.png"></p>

# fastparse

A fast parser for **structured** files. See the [documentation](https://docs.example.test) for details.

.. image:: https://img.shields.io/pypi/v/fastparse.svg
   :target: https://pypi.org/project/fastparse

Features
========
- `parse()` reads a file into rows
"""


def test_badges_images_markup_and_links_are_removed_but_the_words_stay():
    text = clean_doc_text(README)
    assert text.startswith("fastparse A fast parser for **structured** files. See the documentation for details.")
    assert "parse()" in text and "reads a file into rows" in text
    for gone in ("shields.io", "logo.png", "<p", "https://", ":target:", "====", "# "):
        assert gone not in text


def test_pypi_evidence_carries_the_start_of_the_description():
    package = PackageInfo(
        name="fastparse", url="https://pypi.org/project/fastparse/", summary="Fast parsing", version="1.0", license="MIT",
        released=datetime(2026, 1, 1, tzinfo=timezone.utc), source_url=None,
        provenance=Provenance(retrieved_at=datetime(2026, 1, 2, tzinfo=timezone.utc), from_cache=False, requested=True),
        description=README + "word " * 2000,
    )
    _, item = facts_from_pypi(package, "fixture")
    assert item.excerpt.startswith("Fast parsing · version 1.0 · license MIT")
    assert "parse() reads a file into rows" in item.excerpt
    assert len(item.excerpt) < 200 + DOC_EXCERPT_LENGTH  # an excerpt, not the whole description
    assert "package description" in item.excerpt_location


def test_a_package_without_a_description_keeps_the_fields_only():
    package = PackageInfo(
        name="p", url="https://pypi.org/project/p/", summary="S", version="1", license=None, released=None, source_url=None,
        provenance=Provenance(retrieved_at=datetime(2026, 1, 2, tzinfo=timezone.utc), from_cache=False, requested=True),
    )
    _, item = facts_from_pypi(package, "fixture")
    assert item.excerpt == "S · version 1 · license not declared · released release date not reported"


def test_a_long_document_shows_its_opening_and_the_start_of_every_section():
    # Found in a real run: a library's first 1,500 characters were all about its newest feature, so the feature an
    # option relied on (described further down) was not in the evidence.
    readme = (
        "# Tool\nTool is a platform for many things. " + "It does the new thing very well. " * 40
        + "\n## New thing\nThe newest feature. " + "detail " * 80
        + "\n## Experiment tracking\nLog parameters, metrics and artifacts for every run. " + "detail " * 80
        + "\n## Registry\nVersion trained models. " + "detail " * 80
    )
    excerpt, location = doc_excerpt(readme)
    assert len(excerpt) <= DOC_EXCERPT_LENGTH
    assert excerpt.startswith("Tool Tool is a platform")
    assert "Experiment tracking: Log parameters, metrics and artifacts" in excerpt
    assert "Registry: Version trained models" in excerpt
    assert "section" in location


def test_a_short_document_is_kept_whole():
    excerpt, _ = doc_excerpt("# Tool\nA small library.\n## Use\nCall it.")
    assert excerpt == clean_doc_text("# Tool\nA small library.\n## Use\nCall it.")
