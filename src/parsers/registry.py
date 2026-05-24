from pathlib import Path

from .base import BaseParser
from .delimited import CSVParser, TSVParser, PipeParser
from .json_parsers import JSONParser, JSONLParser
from ..exceptions import ParseError


class ParserRegistry:
    def __init__(self):
        self._registry: dict[str, BaseParser] = {
            ".csv": CSVParser(),
            ".tsv": TSVParser(),
            ".psv": PipeParser(),
            ".json": JSONParser(),
            ".jsonl": JSONLParser(),
            ".ndjson": JSONLParser(),
        }

    def get(self, path: Path) -> BaseParser:
        ext = path.suffix.lower()
        if ext not in self._registry:
            supported = ", ".join(sorted(self._registry))
            raise ParseError(
                f"Unsupported file extension '{ext}'. Supported: {supported}"
            )
        return self._registry[ext]
