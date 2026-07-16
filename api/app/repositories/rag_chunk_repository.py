import uuid

from sqlalchemy import Float, delete, func, select, text
from sqlalchemy.orm import Session, joinedload

from app.models.rag_chunk import RAGChunk


class RAGChunkRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def bulk_create(self, chunks: list[RAGChunk]) -> None:
        self.db.add_all(chunks)
        self.db.flush()

    def delete_for_document(self, document_id: uuid.UUID) -> None:
        self.db.execute(delete(RAGChunk).where(RAGChunk.document_id == document_id))
        self.db.flush()

    def vector_search(
        self, query_embedding: list[float], *, limit: int
    ) -> list[tuple[RAGChunk, float]]:
        """Nearest chunks by cosine distance (0 = identical, 2 = opposite)
        -- lower is more similar."""
        distance = RAGChunk.embedding.cosine_distance(query_embedding).label("distance")
        stmt = (
            select(RAGChunk, distance)
            .options(joinedload(RAGChunk.document))
            .order_by(distance)
            .limit(limit)
        )
        return [(chunk, dist) for chunk, dist in self.db.execute(stmt).all()]

    def keyword_search(self, query: str, *, limit: int) -> list[tuple[RAGChunk, float]]:
        """Nearest chunks by Postgres full-text search rank -- higher is
        more relevant (opposite direction from vector_search's distance)."""
        tsquery = func.plainto_tsquery("english", query)
        tsvector = func.to_tsvector("english", RAGChunk.content)
        rank = func.ts_rank(tsvector, tsquery).cast(Float).label("rank")
        stmt = (
            select(RAGChunk, rank)
            .options(joinedload(RAGChunk.document))
            .where(tsvector.op("@@")(tsquery))
            .order_by(text("rank DESC"))
            .limit(limit)
        )
        return [(chunk, rank_value) for chunk, rank_value in self.db.execute(stmt).all()]
