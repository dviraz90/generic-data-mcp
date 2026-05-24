import json

from .base import BaseTool, ToolResult
from ..exceptions import MCPError
from ..storage.sqlite_store import SQLiteStore


class SearchTool(BaseTool):
    @property
    def name(self) -> str:
        return "search"

    @property
    def description(self) -> str:
        return (
            "Full-text keyword search over a table column using FTS5. "
            "Use action='enable' first to index a (table, columns) pair. "
            "Then use action='search' with a keyword query. "
            "For semantic/meaning-based search use vector_search instead."
        )

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["enable", "search"]},
                "table": {"type": "string"},
                "columns": {"type": "array", "items": {"type": "string"}},
                "query": {
                    "type": "string",
                    "description": "Keyword query (for action='search')",
                },
                "limit": {"type": "integer", "default": 20},
            },
            "required": ["action", "table", "columns"],
        }

    def __init__(self, store: SQLiteStore):
        self._store = store

    def run(self, **kwargs) -> ToolResult:
        try:
            action = kwargs["action"]
            table = kwargs["table"]
            columns = kwargs["columns"]

            if action == "enable":
                self._store.search.enable(table, columns)
                return ToolResult(
                    content=f"FTS5 index enabled for '{table}' on {columns}."
                )
            elif action == "search":
                query = kwargs.get("query", "")
                if not query:
                    return ToolResult(
                        content="'query' is required for action='search'.",
                        is_error=True,
                    )
                limit = kwargs.get("limit", 20)
                results = self._store.search.search(table, columns, query, limit)
                return ToolResult(content=json.dumps(results, indent=2))
            else:
                return ToolResult(
                    content=f"Unknown action '{action}'. Use 'enable' or 'search'.",
                    is_error=True,
                )
        except MCPError as e:
            return ToolResult(content=str(e), is_error=True)
