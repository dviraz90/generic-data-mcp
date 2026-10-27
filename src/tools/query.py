from __future__ import annotations

from typing import Any

from src.exceptions import GenericDataMCPError
from src.storage.query import DEFAULT_TIMEOUT_SECONDS
from src.storage.sqlite_store import SQLiteStore
from src.tools.base import BaseTool, ToolResult


class QueryTool(BaseTool):
    name = "query"
    description = (
        "Run a single read-only SELECT statement against the loaded tables. "
        f"Results are capped at 1000 rows, and a query that runs longer than "
        f"{DEFAULT_TIMEOUT_SECONDS:g} seconds is stopped. Only SELECT/WITH...SELECT/UNION are allowed; "
        "call describe_table first if you don't know the schema."
    )
    input_schema = {
        "type": "object",
        "properties": {"sql": {"type": "string"}},
        "required": ["sql"],
    }

    def __init__(self, store: SQLiteStore):
        self._store = store

    def execute(self, arguments: dict[str, Any]) -> ToolResult:
        sql = arguments.get("sql", "")
        try:
            result = self._store.query(sql)
        except GenericDataMCPError as e:
            return ToolResult.fail(str(e))

        return ToolResult.ok(
            columns=result.columns,
            rows=[list(row) for row in result.rows],
            truncated=result.truncated,
        )
