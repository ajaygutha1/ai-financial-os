from app.ai.rag.chunker import chunk_markdown


def test_splits_by_heading_and_prefixes_title_and_section() -> None:
    markdown = """# Emergency Funds

Intro paragraph before any heading.

## How much to save

Three to six months of essential expenses.

## Where to keep it

A high-yield savings account, not invested in the market.
"""
    chunks = chunk_markdown(title="Emergency Fund Guidelines", markdown=markdown)

    assert [c.content.splitlines()[0] for c in chunks] == [
        "Emergency Fund Guidelines",
        "Emergency Fund Guidelines — How much to save",
        "Emergency Fund Guidelines — Where to keep it",
    ]
    assert "Intro paragraph" in chunks[0].content
    assert "Three to six months" in chunks[1].content
    assert "high-yield savings account" in chunks[2].content


def test_document_with_no_headings_is_a_single_chunk() -> None:
    markdown = "# Just A Title\n\nOne short paragraph, no ## sections at all."

    chunks = chunk_markdown(title="No Sections", markdown=markdown)

    assert len(chunks) == 1
    assert chunks[0].content.startswith("No Sections\n\n")
    assert "no ## sections at all" in chunks[0].content


def test_long_section_is_split_into_overlapping_windows() -> None:
    words = [f"word{i}" for i in range(700)]
    markdown = "# Long Doc\n\n## Big Section\n\n" + " ".join(words)

    chunks = chunk_markdown(title="Long Doc", markdown=markdown)

    assert len(chunks) == 3
    # A 50-word overlap means the tail of one window (words 250-299)
    # reappears at the head of the next (words 250-549) -- confirms the
    # sliding window actually overlaps rather than cutting the section into
    # disjoint thirds.
    assert "word295" in chunks[0].content
    assert "word295" in chunks[1].content
    assert "word295" not in chunks[2].content


def test_token_count_is_positive_and_roughly_tracks_length() -> None:
    short = chunk_markdown(title="T", markdown="short text")[0]
    long_markdown = "word " * 500
    long = chunk_markdown(title="T", markdown=long_markdown)[0]

    assert short.token_count > 0
    assert long.token_count > short.token_count
