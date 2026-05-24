from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Iterator


class BaseParser(ABC):
    @abstractmethod
    def parse(self, path: Path) -> Iterator[dict[str, Any]]:
        ...
