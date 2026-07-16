import re
from dataclasses import dataclass

_HEADING_PATTERN = re.compile(r"^##\s+(.+)$", re.MULTILINE)
_TITLE_LINE_PATTERN = re.compile(r"^#\s+.+\n?")
_MAX_WORDS = 300
_OVERLAP_WORDS = 50


@dataclass
class Chunk:
    content: str
    token_count: int


def chunk_markdown(*, title: str, markdown: str) -> list[Chunk]:
    """Splits a markdown document into retrievable chunks: first by `##`
    section, then by a sliding word window for any section still too long.
    Each chunk is prefixed with the document title and section heading so it
    stays meaningful once separated from the rest of the document -- a
    retrieved chunk that just says "3 to 6 months" is useless without
    knowing it's about an emergency fund.
    """
    chunks: list[Chunk] = []
    for heading, body in _split_sections(markdown):
        body = body.strip()
        if not body:
            continue
        prefix = f"{title} — {heading}" if heading else title
        words = body.split()
        if len(words) <= _MAX_WORDS:
            chunks.append(_make_chunk(prefix, body))
            continue

        start = 0
        while start < len(words):
            window = words[start : start + _MAX_WORDS]
            chunks.append(_make_chunk(prefix, " ".join(window)))
            if start + _MAX_WORDS >= len(words):
                break
            start += _MAX_WORDS - _OVERLAP_WORDS
    return chunks


def _make_chunk(prefix: str, body: str) -> Chunk:
    content = f"{prefix}\n\n{body}"
    return Chunk(content=content, token_count=_approx_token_count(content))


def _approx_token_count(text: str) -> int:
    # ~4 chars/token heuristic for English -- good enough for observability,
    # never used for a billing or context-limit decision.
    return max(1, len(text) // 4)


def _split_sections(markdown: str) -> list[tuple[str, str]]:
    """Returns (heading, body) pairs. Content before the first `##` heading
    (typically the doc's `#` title and intro) is returned with an empty
    heading, and the leading `# Title` line is stripped from it."""
    matches = list(_HEADING_PATTERN.finditer(markdown))
    if not matches:
        return [("", markdown)]

    sections: list[tuple[str, str]] = []
    intro = _TITLE_LINE_PATTERN.sub("", markdown[: matches[0].start()], count=1).strip()
    if intro:
        sections.append(("", intro))

    for i, match in enumerate(matches):
        heading = match.group(1).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(markdown)
        sections.append((heading, markdown[start:end]))
    return sections
