from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from src.exceptions import ParseError, UnsupportedFileTypeError
from src.parsers.base import BaseParser


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (dict, list)):
        return json.dumps(value)
    return str(value)


class XLSXParser(BaseParser):
    """Parses an Excel .xlsx workbook's active sheet, treating row 1 as the header."""

    name = "xlsx"
    extensions = (".xlsx",)

    def parse(self, path: Path) -> Iterator[dict[str, str]]:
        try:
            import openpyxl  # noqa: PLC0415 - lazy: openpyxl is an optional [ui] extra
        except ImportError as e:
            raise UnsupportedFileTypeError(
                "Reading '.xlsx' files requires the optional 'openpyxl' dependency. "
                'Install it with: pip install ".[ui]"'
            ) from e

        workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
        try:
            sheet = workbook.active
            rows = sheet.iter_rows(values_only=True)

            try:
                header_row = next(rows)
            except StopIteration as e:
                raise ParseError(f"'{path}' has no header row: the sheet is empty.") from e

            headers = [_stringify(cell) for cell in header_row]
            if not any(h != "" for h in headers):
                raise ParseError(f"'{path}' has no header row: the first row is empty.")

            for raw_row in rows:
                values = [_stringify(cell) for cell in raw_row]
                # Skip fully-empty (trailing) rows.
                if not any(v != "" for v in values):
                    continue
                record: dict[str, str] = {}
                for header, value in zip(headers, values, strict=False):
                    if header == "":
                        continue
                    record[header] = value
                yield record
        finally:
            workbook.close()
