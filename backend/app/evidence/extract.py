"""
Turning a fetched page into a short, quotable excerpt.

What this file does
    html_to_text   strips tags, scripts and styles from a page
    make_excerpt   a short quote plus WHERE in the text it came from
    clean_doc_text a README or package description without badges, images, markup and links, so an excerpt holds
                   what the project DOES instead of its badge row
    doc_excerpt    the excerpt of a README or description: all of it when short; when long, its opening plus the
                   first words of every section, so a library that does many things shows all of them
    sha256_of      a fingerprint of the content, to notice later changes

Why excerpts stay short (but not too short)
    Evidence quotes just enough to show what a claim rests on, and respects
    the source's license. The full text is not stored. Documentation excerpts
    are longer (DOC_EXCERPT_LENGTH) than page excerpts: found in a real run, a
    one-line package summary or the first 400 characters of a README (mostly
    badges) could not support ANY claim, so the options review flagged every
    reused library. A cleaned 1,500 characters covers the overview and the main
    features, but not always: a later run found a library whose first 1,500
    characters were all about its newest feature, while the feature the option
    relied on was described further down. So a long document gives its opening
    plus the start of each section (doc_excerpt).

How it plugs in
    app/research/evidence.py and app/graph/nodes/fetch_docs.py use these.
"""

import hashlib
import re
from html.parser import HTMLParser

EXCERPT_LENGTH = 400
DOC_EXCERPT_LENGTH = 1500


class _TextExtractor(HTMLParser):
    SKIP = {"script", "style", "noscript", "template", "head"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self._skip_depth += 1

    def handle_endtag(self, tag):
        if tag in self.SKIP and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data):
        if not self._skip_depth:
            self.parts.append(data)


def html_to_text(html: str) -> str:
    parser = _TextExtractor()
    parser.feed(html)
    return re.sub(r"\s+", " ", " ".join(parser.parts)).strip()


def tidy_text(text: str) -> str:
    """Collapse runs of whitespace, so an excerpt is one readable paragraph."""
    return re.sub(r"\s+", " ", text).strip()


_BADGE = re.compile(r"\[!\[[^\]]*\]\([^)]*\)\]\([^)]*\)")  # [![alt](image)](link)
_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")  # ![alt](image)
_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")  # [text](link) -> text
_RST_DIRECTIVE = re.compile(r"^\s*\.\. [a-z|-]+[^\n]*$|^\s+:[a-z-]+:[^\n]*$", re.MULTILINE)  # .. image:: / :target:
_RST_SUBSTITUTION = re.compile(r"\|[A-Za-z0-9_ -]+\|_?")  # |badge|
_URL = re.compile(r"https?://\S+")
_HEADING = re.compile(r"^\s{0,3}#{1,6}\s*", re.MULTILINE)
_RULE = re.compile(r"^\s*([=~^*_-])\1{2,}\s*$", re.MULTILINE)  # RST underlines and Markdown rules


def clean_doc_text(text: str) -> str:
    """Documentation as plain sentences: no badges, images, HTML, link targets, bare URLs or heading marks."""
    for pattern in (_BADGE, _IMAGE, _RST_DIRECTIVE, _RULE):
        text = pattern.sub(" ", text)
    text = _LINK.sub(r"\1", text)
    text = re.sub(r"<[^>]+>", " ", text)
    for pattern in (_RST_SUBSTITUTION, _URL, _HEADING):
        text = pattern.sub(" ", text)
    return tidy_text(text.replace("`", ""))  # inline-code marks: the name inside them stays


def make_excerpt(text: str, start: int = 0, length: int = EXCERPT_LENGTH) -> tuple[str, str]:
    """A short quote and its location, e.g. ("A notes app...", "characters 0-58")."""
    end = min(start + length, len(text))
    return text[start:end], f"characters {start}-{end}"


def sha256_of(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# --- Long documents: the opening plus the start of every section ---------------------------------------------------

OPENING_LENGTH = 600  # the overview at the top
SECTION_LENGTH = 150  # each section's heading and first words
_SECTION_START = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$|^\s*<h[1-6][^>]*>(.*?)</h[1-6]>", re.MULTILINE | re.IGNORECASE)


def _sections(text: str) -> list[tuple[str, str]]:
    """(heading, body) for each Markdown or HTML heading, in order; the part before the first one has heading ''."""
    marks = list(_SECTION_START.finditer(text))
    if not marks:
        return [("", text)]
    found = [("", text[: marks[0].start()])]
    for index, mark in enumerate(marks):
        end = marks[index + 1].start() if index + 1 < len(marks) else len(text)
        found.append(((mark.group(1) or mark.group(2) or "").strip(), text[mark.end():end]))
    return found


def doc_excerpt(text: str, length: int = DOC_EXCERPT_LENGTH) -> tuple[str, str]:
    """A README or description as (excerpt, where it came from). See doc_excerpt in the notes at the top."""
    cleaned = clean_doc_text(text) or tidy_text(text)
    if len(cleaned) <= length:
        return cleaned, f"characters 0-{len(cleaned)}"
    sections = _sections(text)
    opening = ""
    parts: list[str] = []
    for heading, body in sections:
        body_text = clean_doc_text(body)
        if not opening:
            # The overview: whatever comes before the second heading (a README usually starts with its title).
            opening = tidy_text(f"{clean_doc_text(heading)} {body_text}")[:OPENING_LENGTH]
            continue
        title = clean_doc_text(heading)
        if not title or not body_text:
            continue
        parts.append(f"{title}: {body_text}"[:SECTION_LENGTH].rstrip() + "…")
    if len(parts) < 2:  # no real sections: the opening characters, as before
        return make_excerpt(cleaned, length=length)
    excerpt = opening.rstrip() + " … "
    for part in parts:
        if len(excerpt) + len(part) + 3 > length:
            break
        excerpt += part + " · "
    return excerpt.rstrip(" ·"), "the opening, then the start of each section"
