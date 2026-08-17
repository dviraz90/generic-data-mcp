from __future__ import annotations

from typing import Any, ClassVar

from src.exceptions import GenericDataMCPError
from src.storage.sqlite_store import SQLiteStore
from src.tools.base import BaseTool, ToolResult


class QueryTool(BaseTool):
    name = "query"
    description = (
        "Run a single read-only SELECT statement against the loaded tables. "
        "Results are capped at 1000 rows. Only SELECT/WITH...SELECT/UNION are allowed; "
        "call describe_table first if you don't know the schema."
    )
    input_schema: ClassVar[dict[str, Any]] = {
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
