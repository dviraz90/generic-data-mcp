from __future__ import annotations

from typing import Any

from src.exceptions import GenericDataMCPError
from src.parsers.registry import ParserRegistry
from src.storage.sqlite_store import SQLiteStore
from src.tools.base import BaseTool, ToolResult
from src.validators.path import PathValidator


class IngestFileTool(BaseTool):
    name = "ingest_file"
    description = (
        "Parse a structured file (CSV, TSV, pipe-delimited, JSON, JSONL) and load it "
        "into a new SQLite table. Call this before query/describe_table/search on a "
        "dataset that hasn't been loaded yet. Choose a short, descriptive table_name "
        "(e.g. 'orders', 'users') matching [A-Za-z_][A-Za-z0-9_]*."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the file. Must resolve under an allowed directory.",
            },
            "table_name": {
                "type": "string",
                "description": "Name for the new SQLite table.",
            },
        },
        "required": ["path", "table_name"],
    }

    def __init__(
        self, store: SQLiteStore, path_validator: PathValidator, parser_registry: ParserRegistry
    ):
        self._store = store
        self._path_validator = path_validator
        self._parsers = parser_registry

    def execute(self, arguments: dict[str, Any]) -> ToolResult:
        path_arg = arguments.get("path", "")
        table_name = arguments.get("table_name", "")

        try:
            resolved_path = self._path_validator.validate(path_arg)
            parser = self._parsers.resolve(resolved_path)
            rows = parser.parse(resolved_path)
            schema = self._store.ingest(table_name, str(resolved_path), rows)
        except GenericDataMCPError as e:
            return ToolResult.fail(str(e))

        return ToolResult.ok(
            table_name=table_name,
            columns=[{"name": c.name, "type": c.sql_type.value} for c in schema.columns],
        )
