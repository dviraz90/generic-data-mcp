import json

from .base import BaseTool, ToolResult
from ..exceptions import MCPError
from ..storage.sqlite_store import SQLiteStore


class VectorSearchTool(BaseTool):
    @property
    def name(self) -> str:
        return "vector_search"

    @property
    def description(self) -> str:
        return (
            "Semantic vector search — finds rows similar in meaning to a query, "
            "even when they share no keywords. "
            "Use action='enable' to index a (table, column) pair (runs once per column). "
            "Use action='search' with a natural-language query string. "
            "Use action='list' to see all enabled vector indexes. "
            "For exact keyword matching use the search tool instead."
        )

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["enable", "search", "list"],
                },
                "table": {"type": "string"},
                "column": {"type": "string"},
                "query": {
                    "type": "string",
                    "description": "Natural-language query (for action='search')",
                },
                "k": {
                    "type": "integer",
                    "default": 10,
                    "description": "Number of results to return",
                },
            },
            "required": ["action"],
        }

    def __init__(self, store: SQLiteStore):
        self._store = store

    def run(self, **kwargs) -> ToolResult:
        if self._store.vector is None:
            return ToolResult(
                content=(
                    "Vector search is not configured. "
                    "Set MCP_EMBED_URL and MCP_EMBED_API_KEY environment variables."
                ),
                is_error=True,
            )
        try:
            action = kwargs["action"]

            if action == "list":
                indexes = self._store.vector.list_indexes()
                return ToolResult(content=json.dumps(indexes, indent=2))

            table = kwargs.get("table")
            column = kwargs.get("column")
            if not table or not column:
                return ToolResult(
                    content="'table' and 'column' are required for this action.",
                    is_error=True,
                )

            if action == "enable":
                count = self._store.vector.enable(table, column)
                return ToolResult(
                    content=(
                        f"Vector index built for '{table}'.'{column}': "
                        f"{count} rows indexed."
                    )
                )
            elif action == "search":
                query = kwargs.get("query", "")
                if not query:
                    return ToolResult(
                        content="'query' is required for action='search'.",
                        is_error=True,
                    )
                k = kwargs.get("k", 10)
                results = self._store.vector.search(table, column, query, k)
                return ToolResult(content=json.dumps(results, indent=2))
            else:
                return ToolResult(
                    content=f"Unknown action '{action}'. Use 'enable', 'search', or 'list'.",
                    is_error=True,
                )
        except MCPError as e:
            return ToolResult(content=str(e), is_error=True)
