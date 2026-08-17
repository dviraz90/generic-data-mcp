from __future__ import annotations

from typing import Any, ClassVar

from src.exceptions import GenericDataMCPError
from src.storage.sqlite_store import SQLiteStore
from src.tools.base import BaseTool, ToolResult


class DescribeTableTool(BaseTool):
    name = "describe_table"
    description = (
        "Show the column names/types and up to 5 sample rows for a loaded table. "
        "Call this before writing a query if you don't know the schema."
    )
    input_schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {"table_name": {"type": "string"}},
        "required": ["table_name"],
    }

    def __init__(self, store: SQLiteStore):
        self._store = store

    def execute(self, arguments: dict[str, Any]) -> ToolResult:
        table_name = arguments.get("table_name", "")
        try:
            schema, sample_rows = self._store.describe_table(table_name)
        except GenericDataMCPError as e:
            return ToolResult.fail(str(e))

        return ToolResult.ok(
            table_name=table_name,
            columns=[{"name": c.name, "type": c.sql_type.value} for c in schema.columns],
            sample_rows=sample_rows,
        )
