import json
from pathlib import Path
from typing import Any, Iterator

from .base import BaseParser
from ..exceptions import ParseError


class JSONParser(BaseParser):
    def parse(self, path: Path) -> Iterator[dict[str, Any]]:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            raise ParseError(f"{path.name}: expected a JSON array of objects")
        for item in data:
            if not isinstance(item, dict):
                raise ParseError(f"{path.name}: each element must be a JSON object")
            yield item


class JSONLParser(BaseParser):
    def parse(self, path: Path) -> Iterator[dict[str, Any]]:
        with path.open(encoding="utf-8") as f:
            for lineno, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError as e:
                    raise ParseError(f"{path.name}:{lineno}: {e}") from e
                if not isinstance(obj, dict):
                    raise ParseError(f"{path.name}:{lineno}: each line must be a JSON object")
                yield obj
