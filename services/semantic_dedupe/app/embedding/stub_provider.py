import hashlib
import random
from app.embedding.base import EmbeddingProvider


class StubEmbeddingProvider(EmbeddingProvider):
    """
    Deterministic pseudo-embedding for tests/dev.
    IMPORTANT: returns 3072 dims to match vector(3072) DB schema.
    """

    def __init__(self, dims: int = 3072, model_name: str = "stub-3072"):
        self._dims = dims
        self._model = model_name

    @property
    def model_name(self) -> str:
        return self._model

    def embed(self, text: str) -> list[float]:
        h = hashlib.sha256(text.encode("utf-8")).digest()
        seed = int.from_bytes(h[:8], "big", signed=False)
        rng = random.Random(seed)
        return [rng.random() for _ in range(self._dims)]

