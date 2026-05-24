import json

from .base import BaseTool, ToolResult
from ..exceptions import MCPError
from ..storage.sqlite_store import SQLiteStore


class DescribeTableTool(BaseTool):
    @property
    def name(self) -> str:
        return "describe_table"

    @property
    def description(self) -> str:
        return (
            "Show the schema and first 5 sample rows for a table. "
            "Call this before query if you don't know the column names or types. "
            "Use list_datasets to find available table names."
        )

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "table_name": {
                    "type": "string",
                    "description": "Name of the table to describe",
                },
            },
            "required": ["table_name"],
        }

    def __init__(self, store: SQLiteStore):
        self._store = store

    def run(self, **kwargs) -> ToolResult:
        table = kwargs["table_name"]
        try:
            schema = self._store.tables.get_schema(table)
            if not schema:
                return ToolResult(
                    content=(
                        f"Table '{table}' not found. "
                        "Use list_datasets to see available tables."
                    ),
                    is_error=True,
                )
            sample = self._store.query.execute(f'SELECT * FROM "{table}" LIMIT 5')
            return ToolResult(
                content=json.dumps({"schema": schema, "sample": sample}, indent=2)
            )
        except MCPError as e:
            return ToolResult(content=str(e), is_error=True)
