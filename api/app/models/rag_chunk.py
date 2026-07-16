import uuid
from typing import TYPE_CHECKING

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, Index, Integer, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.base import TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from app.models.rag_document import RAGDocument

# fastembed's default model (BAAI/bge-small-en-v1.5) produces 384-dim vectors.
# Fixed here rather than made configurable -- changing embedding models means
# re-embedding the whole corpus anyway, so this isn't a runtime knob.
EMBEDDING_DIMENSIONS = 384


class RAGChunk(UUIDPKMixin, TimestampMixin, Base):
    """One retrievable unit of a RAGDocument. Chunks (not whole documents)
    are what get embedded and searched -- keeps each vector focused on one
    topic and keeps retrieved context small enough to actually cite."""

    __tablename__ = "rag_chunk"
    __table_args__ = (
        Index("ix_rag_chunk_document_id", "document_id"),
        Index(
            "ix_rag_chunk_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        # Keyword side of hybrid retrieval -- a functional GIN index rather
        # than a stored generated column, since the corpus is small enough
        # that computing to_tsvector at query/index time isn't a bottleneck.
        Index(
            "ix_rag_chunk_content_fts",
            text("to_tsvector('english', content)"),
            postgresql_using="gin",
        ),
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rag_document.id", ondelete="CASCADE"), nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIMENSIONS), nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)

    document: Mapped["RAGDocument"] = relationship()
