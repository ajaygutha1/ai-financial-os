from abc import ABC, abstractmethod


class EmbeddingProvider(ABC):
    """Every RAG component talks to this interface, never a concrete
    embedding library directly -- mirrors the AIProvider adapter pattern
    from Milestone 4. Swapping embedding backends later (or adding a hosted
    provider like Voyage AI) means writing one new adapter class, no changes
    to ingestion or retrieval code."""

    @property
    @abstractmethod
    def dimensions(self) -> int: ...

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]: ...
