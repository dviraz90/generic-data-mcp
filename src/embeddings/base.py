from abc import ABC, abstractmethod


class BaseEmbedder(ABC):
    @property
    @abstractmethod
    def model_name(self) -> str: ...

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]: ...
