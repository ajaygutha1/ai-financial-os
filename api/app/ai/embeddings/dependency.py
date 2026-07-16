from functools import lru_cache

from app.ai.embeddings.base import EmbeddingProvider
from app.ai.embeddings.fastembed_provider import FastEmbedProvider


@lru_cache
def _singleton() -> FastEmbedProvider:
    # Constructing FastEmbedProvider loads an ONNX model -- cache it as a
    # process-wide singleton rather than reloading per request.
    return FastEmbedProvider()


def get_embedding_provider() -> EmbeddingProvider:
    """FastAPI dependency, overridden in tests with a FakeEmbeddingProvider
    -- same seam as ai/provider/dependency.py."""
    return _singleton()
