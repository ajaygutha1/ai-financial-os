from sqlalchemy.orm import Session

from app.ai.embeddings.fake_provider import FakeEmbeddingProvider
from app.ai.rag.retrieval import HybridRetriever
from app.models.rag_chunk import RAGChunk
from app.repositories.rag_chunk_repository import RAGChunkRepository
from app.repositories.rag_document_repository import RAGDocumentRepository

_EMBEDDINGS = FakeEmbeddingProvider()


def _seed_document(db: Session, *, title: str, category: str, content: str) -> None:
    doc_repo = RAGDocumentRepository(db)
    document = doc_repo.create(
        title=title,
        source="test-fixture",
        category=category,
        source_url=None,
        content_hash=title,
    )
    chunk_repo = RAGChunkRepository(db)
    embedding = _EMBEDDINGS.embed([content])[0]
    chunk_repo.bulk_create(
        [
            RAGChunk(
                document_id=document.id,
                chunk_index=0,
                content=content,
                embedding=embedding,
                token_count=len(content) // 4,
            )
        ]
    )
    db.commit()


def test_keyword_and_vector_signals_both_surface_the_matching_document(
    db_session: Session,
) -> None:
    _seed_document(
        db_session,
        title="Emergency Fund Guidelines",
        category="emergency_fund",
        content="An emergency fund should cover three to six months of essential expenses.",
    )
    _seed_document(
        db_session,
        title="Debt Payoff Strategies",
        category="debt",
        content="The avalanche method pays off the highest interest rate debt first.",
    )

    retriever = HybridRetriever(db_session, _EMBEDDINGS)
    results = retriever.search("emergency fund months of expenses", top_k=5)

    assert results[0].document_title == "Emergency Fund Guidelines"


def test_category_filter_excludes_non_matching_documents(db_session: Session) -> None:
    _seed_document(
        db_session,
        title="Emergency Fund Guidelines",
        category="emergency_fund",
        content="An emergency fund should cover three to six months of essential expenses.",
    )
    _seed_document(
        db_session,
        title="Debt Payoff Strategies",
        category="debt",
        content="The avalanche method pays off the highest interest rate debt first.",
    )

    retriever = HybridRetriever(db_session, _EMBEDDINGS)
    results = retriever.search("expenses debt interest", top_k=5, category="emergency_fund")

    assert all(r.document_title == "Emergency Fund Guidelines" for r in results)


def test_category_filter_finds_a_match_outside_the_corpus_wide_top_candidates(
    db_session: Session,
) -> None:
    # Regression: category filtering used to happen *after* fusing the
    # corpus-wide top-20-per-leg pull, so a real match in the requested
    # category that doesn't rank in that top 20 (because a different
    # category dominates the corpus for this query) was silently dropped --
    # not just deprioritized, excluded entirely, even though it's the only
    # document in the requested category. Seed enough same-vocabulary decoys
    # in a different category to push the real match past the top-20 cutoff
    # in both the vector and keyword legs.
    query = "emergency fund months expenses coverage"
    for i in range(25):
        _seed_document(
            db_session,
            title=f"Budgeting Decoy {i}",
            category="budgeting",
            content=query,
        )
    _seed_document(
        db_session,
        title="Emergency Fund Guidelines",
        category="emergency_fund",
        content="keep three months of essential spending saved for surprises",
    )

    retriever = HybridRetriever(db_session, _EMBEDDINGS)
    results = retriever.search(query, top_k=5, category="emergency_fund")

    assert len(results) == 1
    assert results[0].document_title == "Emergency Fund Guidelines"


def test_top_k_limits_the_number_of_results(db_session: Session) -> None:
    for i in range(8):
        _seed_document(
            db_session,
            title=f"Budgeting Doc {i}",
            category="budgeting",
            content="Budgeting frameworks help allocate income across categories every month.",
        )

    retriever = HybridRetriever(db_session, _EMBEDDINGS)
    results = retriever.search("budgeting income categories", top_k=3)

    assert len(results) == 3
