from app.config import EMBEDDINGS_PROVIDER
from app.embedding.openai_provider import OpenAIEmbeddingProvider
from app.embedding.stub_provider import StubEmbeddingProvider

_provider = None

def get_embedding_provider():
    """
    Singleton-ish provider factory.
    """
    global _provider
    if _provider is not None:
        return _provider

    if EMBEDDINGS_PROVIDER == "stub":
        _provider = StubEmbeddingProvider()
        return _provider

    # default
    _provider = OpenAIEmbeddingProvider()
    return _provider

