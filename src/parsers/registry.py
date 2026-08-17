from __future__ import annotations

from pathlib import Path

from src.exceptions import UnsupportedFileTypeError
from src.parsers.base import BaseParser
from src.parsers.delimited import CSVParser, PipeDelimitedParser, TSVParser
from src.parsers.json_parsers import JSONLParser, JSONParser
from src.parsers.xlsx import XLSXParser


class ParserRegistry:
    """Resolves a file path to the parser registered for its extension."""

    def __init__(self):
        self._parsers: dict[str, BaseParser] = {}
        for parser in (
            CSVParser(),
            TSVParser(),
            PipeDelimitedParser(),
            JSONParser(),
            JSONLParser(),
            XLSXParser(),
        ):
            self.register(parser)

    def register(self, parser: BaseParser) -> None:
        for ext in parser.extensions:
            self._parsers[ext.lower()] = parser

    def resolve(self, path: Path) -> BaseParser:
        ext = path.suffix.lower()
        parser = self._parsers.get(ext)
        if parser is None:
            supported = ", ".join(sorted(self._parsers))
            raise UnsupportedFileTypeError(
                f"No parser registered for '{ext}'. Supported extensions: {supported}."
            )
        return parser
