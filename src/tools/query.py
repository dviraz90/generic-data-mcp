import json

from .base import BaseTool, ToolResult
from ..exceptions import MCPError
from ..storage.sqlite_store import SQLiteStore


class QueryTool(BaseTool):
    @property
    def name(self) -> str:
        return "query"

    @property
    def description(self) -> str:
        return (
            "Run a read-only SELECT statement against a loaded dataset. "
            "Results are capped at 1000 rows. "
            "Call describe_table first if you don't know the schema. "
            "Only SELECT is allowed — no INSERT, UPDATE, DROP, or DDL."
        )

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "sql": {
                    "type": "string",
                    "description": "A single SELECT SQL statement",
                },
            },
            "required": ["sql"],
        }

    def __init__(self, store: SQLiteStore):
        self._store = store

    def run(self, **kwargs) -> ToolResult:
        try:
            rows = self._store.query.execute(kwargs["sql"])
            return ToolResult(content=json.dumps(rows, indent=2))
        except MCPError as e:
            return ToolResult(content=str(e), is_error=True)
