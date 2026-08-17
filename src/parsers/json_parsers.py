from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from src.exceptions import ParseError
from src.parsers.base import BaseParser


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (dict, list)):
        return json.dumps(value)
    return str(value)


class JSONParser(BaseParser):
    """Parses a JSON file containing an array of objects (or a single object)."""

    name = "json"
    extensions = (".json",)

    def parse(self, path: Path) -> Iterator[dict[str, str]]:
        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise ParseError(f"'{path}' is not valid JSON: {e}") from e

        if isinstance(data, dict):
            data = [data]
        if not isinstance(data, list):
            raise ParseError(
                f"'{path}' must contain a JSON array of objects or a single object."
            )

        for i, record in enumerate(data):
            if not isinstance(record, dict):
                raise ParseError(f"'{path}' element {i} is not a JSON object.")
            yield {k: _stringify(v) for k, v in record.items()}


class JSONLParser(BaseParser):
    """Parses a JSON Lines file: one JSON object per line."""

    name = "jsonl"
    extensions = (".jsonl", ".ndjson")

    def parse(self, path: Path) -> Iterator[dict[str, str]]:
        with path.open("r", encoding="utf-8") as f:
            for line_no, raw_line in enumerate(f, start=1):
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as e:
                    raise ParseError(f"'{path}' line {line_no} is not valid JSON: {e}") from e
                if not isinstance(record, dict):
                    raise ParseError(f"'{path}' line {line_no} is not a JSON object.")
                yield {k: _stringify(v) for k, v in record.items()}
