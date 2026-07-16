from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.embeddings.fake_provider import FakeEmbeddingProvider
from app.ai.rag.ingest import RAGIngestionService
from app.models.rag_document import RAGDocument

_EMBEDDINGS = FakeEmbeddingProvider()


def test_editing_a_documents_title_updates_in_place_instead_of_orphaning(
    db_session: Session, tmp_path: Path
) -> None:
    # Regression: identity used to be keyed on the title text extracted from
    # the document's own `# Heading` line. An edit that changes that line --
    # an ordinary reword, not a rename of the file -- meant the old
    # document+chunks were never found on re-ingestion, so they were left
    # behind as permanent orphans instead of being replaced.
    doc_path = tmp_path / "guide.md"
    doc_path.write_text(
        "# Emergency Fund Guidelines\n\nKeep three months of expenses saved.\n",
        encoding="utf-8",
    )

    service = RAGIngestionService(db_session, _EMBEDDINGS)
    first_outcome = service.ingest_file(doc_path)
    db_session.commit()
    assert first_outcome == "ingested"

    # Reword the title line (and the body, so the content hash also changes
    # and this doesn't just hit the "skipped" no-op path) without renaming
    # the file on disk.
    doc_path.write_text(
        "# Emergency Fund Basics\n\nKeep three to six months of expenses saved.\n",
        encoding="utf-8",
    )

    second_outcome = service.ingest_file(doc_path)
    db_session.commit()
    assert second_outcome == "updated"

    documents = list(db_session.scalars(select(RAGDocument)))
    assert len(documents) == 1
    assert documents[0].title == "Emergency Fund Basics"


def test_reingesting_unchanged_file_is_a_no_op(db_session: Session, tmp_path: Path) -> None:
    doc_path = tmp_path / "guide.md"
    doc_path.write_text(
        "# Emergency Fund Guidelines\n\nKeep three months of expenses saved.\n",
        encoding="utf-8",
    )

    service = RAGIngestionService(db_session, _EMBEDDINGS)
    service.ingest_file(doc_path)
    db_session.commit()

    outcome = service.ingest_file(doc_path)
    db_session.commit()

    assert outcome == "skipped"
    documents = list(db_session.scalars(select(RAGDocument)))
    assert len(documents) == 1
