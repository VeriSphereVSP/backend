from openai import OpenAI

from app.config import OPENAI_API_KEY, EMBEDDINGS_MODEL
from app.embedding.base import EmbeddingProvider


class OpenAIEmbeddingProvider(EmbeddingProvider):
    def __init__(self):
        if not OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY is not set")

        self.client = OpenAI(
            api_key=OPENAI_API_KEY,
            timeout=20.0,
        )

    @property
    def model_name(self) -> str:
        return EMBEDDINGS_MODEL

    def embed(self, text: str) -> list[float]:
        try:
            resp = self.client.embeddings.create(
                model=EMBEDDINGS_MODEL,
                input=text,
            )
            return list(resp.data[0].embedding)
        except Exception as e:
            raise RuntimeError(f"OpenAI embedding failed: {e}") from e

