from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterator

from src.exceptions import ParseError
from src.parsers.base import BaseParser


class DelimitedParser(BaseParser):
    """Parses delimited text files with a header row (CSV, TSV, pipe-delimited)."""

    def __init__(self, name: str, extensions: tuple[str, ...], delimiter: str):
        self.name = name
        self.extensions = extensions
        self._delimiter = delimiter

    def parse(self, path: Path) -> Iterator[dict[str, str]]:
        try:
            with path.open("r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f, delimiter=self._delimiter)
                if reader.fieldnames is None:
                    raise ParseError(f"'{path}' has no header row.")
                for row in reader:
                    yield {k: ("" if v is None else v) for k, v in row.items()}
        except csv.Error as e:
            raise ParseError(f"Failed to parse '{path}': {e}") from e
        except UnicodeDecodeError as e:
            raise ParseError(f"'{path}' is not valid UTF-8: {e}") from e


class CSVParser(DelimitedParser):
    def __init__(self):
        super().__init__(name="csv", extensions=(".csv",), delimiter=",")


class TSVParser(DelimitedParser):
    def __init__(self):
        super().__init__(name="tsv", extensions=(".tsv",), delimiter="\t")


class PipeDelimitedParser(DelimitedParser):
    def __init__(self):
        super().__init__(name="pipe", extensions=(".psv", ".pipe"), delimiter="|")
