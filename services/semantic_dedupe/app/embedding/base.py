from abc import ABC, abstractmethod
from typing import List

class EmbeddingProvider(ABC):
    """
    Minimal embedding provider interface.
    Must return a vector of floats whose dimension matches the DB schema.
    """

    @property
    @abstractmethod
    def model_name(self) -> str:
        ...

    @abstractmethod
    def embed(self, text: str) -> List[float]:
        ...


