from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Any, Iterator

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

    # Ratio is only enforced above this size: tiny highly-compressible sheets are
    # harmless, and legitimate repetitive data can compress very well.
    _RATIO_CHECK_FLOOR = 50 * 1024 * 1024

    def __init__(self, max_uncompressed_bytes: int = 1024**3, max_ratio: int = 100):
        self._max_uncompressed = max_uncompressed_bytes
        self._max_ratio = max_ratio

    def _check_zip_size(self, path: Path) -> None:
        """Refuse zip bombs before openpyxl inflates anything."""
        try:
            with zipfile.ZipFile(path) as archive:
                infos = archive.infolist()
        except zipfile.BadZipFile as e:
            raise ParseError(f"'{path}' is not a valid .xlsx workbook: {e}") from e
        uncompressed = sum(i.file_size for i in infos)
        compressed = max(sum(i.compress_size for i in infos), 1)
        if uncompressed > self._max_uncompressed:
            raise ParseError(
                f"'{path}' expands to {uncompressed:,} bytes, over the "
                f"{self._max_uncompressed:,}-byte limit. Export the sheet to CSV instead."
            )
        if uncompressed > self._RATIO_CHECK_FLOOR and uncompressed / compressed > self._max_ratio:
            raise ParseError(
                f"'{path}' has a suspicious compression ratio "
                f"({uncompressed // compressed}x); refusing to open it. Export the sheet to CSV."
            )

    def parse(self, path: Path) -> Iterator[dict[str, str]]:
        try:
            import openpyxl
        except ImportError as e:
            raise UnsupportedFileTypeError(
                "Reading '.xlsx' files requires the optional 'openpyxl' dependency. "
                'Install it with: pip install ".[ui]"'
            ) from e

        self._check_zip_size(path)
        workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
        try:
            sheet = workbook.active
            rows = sheet.iter_rows(values_only=True)

            try:
                header_row = next(rows)
            except StopIteration:
                raise ParseError(f"'{path}' has no header row: the sheet is empty.")

            headers = [_stringify(cell) for cell in header_row]
            if not any(h != "" for h in headers):
                raise ParseError(f"'{path}' has no header row: the first row is empty.")

            for raw_row in rows:
                values = [_stringify(cell) for cell in raw_row]
                # Skip fully-empty (trailing) rows.
                if not any(v != "" for v in values):
                    continue
                record: dict[str, str] = {}
                for header, value in zip(headers, values):
                    if header == "":
                        continue
                    record[header] = value
                yield record
        finally:
            workbook.close()
