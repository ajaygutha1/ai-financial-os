from fastembed import TextEmbedding

from app.ai.embeddings.base import EmbeddingProvider

# ONNX-based (via fastembed), not sentence-transformers -- equivalent local,
# no-API-key embeddings without pulling in PyTorch, which would otherwise add
# several hundred MB to the API image for no benefit here. 384 dimensions,
# matches RAGChunk.embedding's fixed Vector(384) column.
MODEL_NAME = "BAAI/bge-small-en-v1.5"
DIMENSIONS = 384


class FastEmbedProvider(EmbeddingProvider):
    """Local, in-process embeddings. Constructing this loads an ONNX model
    (downloads on first use, then cached) -- expensive enough that callers
    should hold one instance for the process lifetime rather than
    constructing it per-request; see embeddings/dependency.py."""

    def __init__(self) -> None:
        self._model = TextEmbedding(model_name=MODEL_NAME)

    @property
    def dimensions(self) -> int:
        return DIMENSIONS

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return [vector.tolist() for vector in self._model.embed(texts)]
