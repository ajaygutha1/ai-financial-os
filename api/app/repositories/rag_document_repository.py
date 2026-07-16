from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.rag_document import RAGDocument


class RAGDocumentRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_content_hash(self, content_hash: str) -> RAGDocument | None:
        stmt = select(RAGDocument).where(RAGDocument.content_hash == content_hash)
        return self.db.scalar(stmt)

    def get_by_title(self, title: str) -> RAGDocument | None:
        stmt = select(RAGDocument).where(RAGDocument.title == title)
        return self.db.scalar(stmt)

    def create(
        self,
        *,
        title: str,
        source: str,
        category: str | None,
        source_url: str | None,
        content_hash: str,
    ) -> RAGDocument:
        document = RAGDocument(
            title=title,
            source=source,
            category=category,
            source_url=source_url,
            content_hash=content_hash,
        )
        self.db.add(document)
        self.db.flush()
        return document

    def delete(self, document: RAGDocument) -> None:
        self.db.delete(document)
        self.db.flush()
