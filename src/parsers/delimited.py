import csv
from pathlib import Path
from typing import Any, Iterator

from .base import BaseParser


class DelimitedParser(BaseParser):
    def __init__(self, delimiter: str):
        self._delimiter = delimiter

    def parse(self, path: Path) -> Iterator[dict[str, Any]]:
        with path.open(newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f, delimiter=self._delimiter)
            for row in reader:
                yield dict(row)


class CSVParser(DelimitedParser):
    def __init__(self):
        super().__init__(",")


class TSVParser(DelimitedParser):
    def __init__(self):
        super().__init__("\t")


class PipeParser(DelimitedParser):
    def __init__(self):
        super().__init__("|")
