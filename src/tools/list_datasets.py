import json

from .base import BaseTool, ToolResult
from ..storage.sqlite_store import SQLiteStore


class ListDatasetsTool(BaseTool):
    @property
    def name(self) -> str:
        return "list_datasets"

    @property
    def description(self) -> str:
        return (
            "List all datasets currently loaded in the database. "
            "Returns table names, row counts, and source file paths. "
            "Call this first to discover what data is available before querying."
        )

    @property
    def input_schema(self) -> dict:
        return {"type": "object", "properties": {}}

    def __init__(self, store: SQLiteStore):
        self._store = store

    def run(self, **kwargs) -> ToolResult:
        datasets = self._store.metadata.list_datasets()
        if not datasets:
            return ToolResult(
                content="No datasets loaded. Use ingest_file to load data."
            )
        rows = [
            {"table": d.table_name, "rows": d.row_count, "source": d.source_path}
            for d in datasets
        ]
        return ToolResult(content=json.dumps(rows, indent=2))
