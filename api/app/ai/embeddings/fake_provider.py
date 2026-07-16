import hashlib
import math
import re

from app.ai.embeddings.base import EmbeddingProvider

_WORD_PATTERN = re.compile(r"[a-z0-9]+")


class FakeEmbeddingProvider(EmbeddingProvider):
    """Deterministic hashing-trick bag-of-words vectors, not a real semantic
    model -- but unlike a pure text hash, two texts sharing vocabulary land
    closer together in cosine distance than two that don't. Good enough to
    test that retrieval ranking genuinely responds to content, without
    downloading or running the real ONNX model in every test."""

    def __init__(self, dimensions: int = 384) -> None:
        self._dimensions = dimensions

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        vector = [0.0] * self._dimensions
        for word in _WORD_PATTERN.findall(text.lower()):
            index = int(hashlib.sha256(word.encode("utf-8")).hexdigest(), 16) % self._dimensions
            vector[index] += 1.0
        norm = math.sqrt(sum(v * v for v in vector)) or 1.0
        return [v / norm for v in vector]
