"""Ingests the reference corpus (docs/rag-corpus/*.md) into rag_document/
rag_chunk. Run with: `uv run python -m app.ai.rag.ingest` from api/.

Idempotent: a document whose content hash hasn't changed is skipped; a
document that has changed has its old chunks replaced with freshly chunked
and re-embedded ones. Safe to re-run any time the corpus is edited.
"""

import hashlib
import logging
from pathlib import Path

from sqlalchemy.orm import Session

from app.ai.embeddings.base import EmbeddingProvider
from app.ai.rag.chunker import chunk_markdown
from app.models.rag_chunk import RAGChunk
from app.repositories.rag_chunk_repository import RAGChunkRepository
from app.repositories.rag_document_repository import RAGDocumentRepository

logger = logging.getLogger(__name__)

SOURCE_REFERENCE_CORPUS = "reference_corpus"

# Filename -> category. Explicit rather than parsed from the filename, since
# there are only a handful of documents and an explicit mapping is clearer
# to maintain than fragile string-splitting rules.
_CATEGORY_BY_FILENAME = {
    "emergency-fund-guidelines.md": "emergency_fund",
    "debt-payoff-strategies.md": "debt",
    "retirement-accounts-basics.md": "retirement",
    "tax-brackets-and-marginal-rates.md": "tax",
    "diversification-and-asset-allocation.md": "investing",
    "budgeting-frameworks.md": "budgeting",
}


def _extract_title(markdown: str, fallback: str) -> str:
    for line in markdown.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


class RAGIngestionService:
    def __init__(self, db: Session, embeddings: EmbeddingProvider) -> None:
        self.db = db
        self.embeddings = embeddings
        self.documents = RAGDocumentRepository(db)
        self.chunks = RAGChunkRepository(db)

    def ingest_directory(self, directory: Path) -> dict[str, int]:
        """Returns counts of documents ingested/updated/skipped, for the
        CLI summary and for tests to assert against."""
        result = {"ingested": 0, "updated": 0, "skipped": 0}
        for path in sorted(directory.glob("*.md")):
            if path.name == "README.md":
                continue
            outcome = self.ingest_file(path)
            result[outcome] += 1
        return result

    def ingest_file(self, path: Path) -> str:
        markdown = path.read_text(encoding="utf-8")
        content_hash = hashlib.sha256(markdown.encode("utf-8")).hexdigest()

        if self.documents.get_by_content_hash(content_hash) is not None:
            return "skipped"

        title = _extract_title(markdown, fallback=path.stem)
        category = _CATEGORY_BY_FILENAME.get(path.name)

        # Identity must be the filename, not the title text extracted from
        # the document's own `# Heading` line -- title is content, and an
        # ordinary edit (a reword, a typo fix, a case change) changes it.
        # Keying "is this an update" off title meant such an edit silently
        # orphaned the old document+chunks instead of replacing them,
        # breaking the "old chunks replaced" guarantee in
        # docs/rag-corpus/README.md. The filename is the one thing that
        # stays stable across a content edit.
        source_url = path.name
        existing = self.documents.get_by_source_url(source_url)
        outcome = "updated" if existing is not None else "ingested"
        if existing is not None:
            # Content changed since last ingestion -- replace wholesale
            # rather than diff chunk-by-chunk; the corpus is small and
            # re-embedding a whole document is cheap.
            self.documents.delete(existing)

        document = self.documents.create(
            title=title,
            source=SOURCE_REFERENCE_CORPUS,
            category=category,
            source_url=source_url,
            content_hash=content_hash,
        )

        chunks = chunk_markdown(title=title, markdown=markdown)
        if not chunks:
            return outcome

        vectors = self.embeddings.embed([c.content for c in chunks])
        rows = [
            RAGChunk(
                document_id=document.id,
                chunk_index=i,
                content=chunk.content,
                embedding=vector,
                token_count=chunk.token_count,
            )
            for i, (chunk, vector) in enumerate(zip(chunks, vectors, strict=True))
        ]
        self.chunks.bulk_create(rows)
        return outcome


def main() -> None:
    logging.basicConfig(level=logging.INFO)

    from app.ai.embeddings.fastembed_provider import FastEmbedProvider
    from app.core.db import SessionLocal

    corpus_dir = Path(__file__).resolve().parents[4] / "docs" / "rag-corpus"
    db = SessionLocal()
    try:
        service = RAGIngestionService(db, FastEmbedProvider())
        counts = service.ingest_directory(corpus_dir)
        db.commit()
        logger.info(
            "Ingestion complete: %d ingested, %d updated, %d skipped",
            counts["ingested"],
            counts["updated"],
            counts["skipped"],
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
