from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from pathlib import Path


class BaseParser(ABC):
    """Strategy base class for file parsers.

    Subclasses yield rows as dict[str, str] — raw, uncoerced values. Type
    inference happens later, in the storage layer.
    """

    name: str
    extensions: tuple[str, ...]

    @abstractmethod
    def parse(self, path: Path) -> Iterator[dict[str, str]]:
        raise NotImplementedError
