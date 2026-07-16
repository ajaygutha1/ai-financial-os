from sqlalchemy import Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import TimestampMixin, UUIDPKMixin


class RAGDocument(UUIDPKMixin, TimestampMixin, Base):
    """A source document in the RAG knowledge base (a reference-corpus
    article now; a real IRS/SEC PDF or URL later -- `source`/`source_url`
    exist from day one so ingesting real documents is additive, not a
    redesign, same expand-later pattern as M1/M2's schema choices)."""

    __tablename__ = "rag_document"
    __table_args__ = (
        Index("ix_rag_document_category", "category"),
        Index("ix_rag_document_content_hash", "content_hash", unique=True),
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    # sha256 of the full document content -- re-ingesting an unchanged file
    # is a no-op instead of creating duplicate chunks.
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
