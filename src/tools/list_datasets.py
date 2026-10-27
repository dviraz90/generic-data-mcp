from __future__ import annotations

from typing import Any, ClassVar

from src.storage.sqlite_store import SQLiteStore
from src.tools.base import BaseTool, ToolResult


class ListDatasetsTool(BaseTool):
    name = "list_datasets"
    description = (
        "List every dataset currently loaded into SQLite, with row counts and source "
        "file paths. Call this first if you don't know what data is available."
    )
    input_schema: ClassVar[dict[str, Any]] = {"type": "object", "properties": {}}

    def __init__(self, store: SQLiteStore):
        self._store = store

    def execute(self, arguments: dict[str, Any]) -> ToolResult:
        datasets = self._store.list_datasets()
        return ToolResult.ok(
            datasets=[
                {
                    "table_name": d.table_name,
                    "source_path": d.source_path,
                    "row_count": d.row_count,
                    "ingested_at": d.ingested_at,
                }
                for d in datasets
            ]
        )
