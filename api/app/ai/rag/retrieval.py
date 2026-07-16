import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.ai.embeddings.base import EmbeddingProvider
from app.repositories.rag_chunk_repository import RAGChunkRepository

# Reciprocal Rank Fusion constant -- the standard default from the original
# RRF paper, not tuned for this corpus specifically.
_RRF_K = 60
# Candidates pulled from *each* retrieval method before fusion; top_k (what
# the caller actually gets back) is applied after fusing and filtering.
_CANDIDATES_PER_METHOD = 20


@dataclass
class RetrievedChunk:
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_title: str
    content: str
    score: float


class HybridRetriever:
    """Combines pgvector cosine similarity and Postgres full-text search via
    Reciprocal Rank Fusion -- fusing on rank position rather than trying to
    normalize and blend two incompatible raw scores (cosine distance vs.
    ts_rank), a standard, simple, effective hybrid-search technique."""

    def __init__(self, db: Session, embeddings: EmbeddingProvider) -> None:
        self.db = db
        self.embeddings = embeddings
        self.chunks = RAGChunkRepository(db)

    def search(
        self, query: str, *, top_k: int = 5, category: str | None = None
    ) -> list[RetrievedChunk]:
        query_embedding = self.embeddings.embed([query])[0]
        # category is pushed down into both legs' SQL (pre-LIMIT), not
        # applied here after fusion -- filtering post-fetch on a
        # corpus-wide top-N pull silently under-returns (or returns
        # nothing) once a category's matching chunks don't happen to rank
        # in that top N, even when matching content exists in the DB.
        vector_results = self.chunks.vector_search(
            query_embedding, limit=_CANDIDATES_PER_METHOD, category=category
        )
        keyword_results = self.chunks.keyword_search(
            query, limit=_CANDIDATES_PER_METHOD, category=category
        )

        fused_scores: dict[uuid.UUID, float] = {}
        chunks_by_id = {}
        for result_list in (vector_results, keyword_results):
            for rank, (chunk, _raw_score) in enumerate(result_list):
                fused_scores[chunk.id] = fused_scores.get(chunk.id, 0.0) + 1.0 / (_RRF_K + rank + 1)
                chunks_by_id[chunk.id] = chunk

        ordered_ids = sorted(fused_scores, key=lambda cid: fused_scores[cid], reverse=True)[:top_k]

        return [
            RetrievedChunk(
                chunk_id=chunk_id,
                document_id=chunks_by_id[chunk_id].document_id,
                document_title=chunks_by_id[chunk_id].document.title,
                content=chunks_by_id[chunk_id].content,
                score=fused_scores[chunk_id],
            )
            for chunk_id in ordered_ids
        ]
