from __future__ import annotations

from typing import Any

from src.exceptions import GenericDataMCPError
from src.storage.sqlite_store import SQLiteStore
from src.tools.base import BaseTool, ToolResult

# Same ceiling as the query tool's row cap, so search can't be used to pull an
# unbounded result set that query would refuse.
_MAX_RESULTS = 1000


class SearchTool(BaseTool):
    name = "search"
    description = (
        "Full-text keyword search over a table. Two actions: 'enable' indexes a "
        "(table_name, columns) pair with FTS5 — call this once before searching a "
        "table; 'search' runs a keyword query against an already-enabled table."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["enable", "search"]},
            "table_name": {"type": "string"},
            "columns": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Required for the 'enable' action.",
            },
            "query": {"type": "string", "description": "Required for the 'search' action."},
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": _MAX_RESULTS,
                "description": f"Max results for 'search', default 50, capped at {_MAX_RESULTS}.",
            },
        },
        "required": ["action", "table_name"],
    }

    def __init__(self, store: SQLiteStore):
        self._store = store

    def execute(self, arguments: dict[str, Any]) -> ToolResult:
        action = arguments.get("action")
        table_name = arguments.get("table_name", "")

        try:
            if action == "enable":
                columns = arguments.get("columns") or []
                if not columns:
                    return ToolResult.fail(
                        "The 'enable' action requires a non-empty 'columns' list."
                    )
                fts_table = self._store.enable_search(table_name, columns)
                return ToolResult.ok(table_name=table_name, columns=columns, index=fts_table)

            if action == "search":
                query = arguments.get("query", "")
                if not query:
                    return ToolResult.fail("The 'search' action requires a non-empty 'query' string.")
                limit = arguments.get("limit", 50)
                # bool is an int subclass; True would otherwise pass as limit=1.
                if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
                    return ToolResult.fail(
                        f"'limit' must be a positive integer (at most {_MAX_RESULTS})."
                    )
                limit = min(limit, _MAX_RESULTS)
                results = self._store.search(table_name, query, limit)
                return ToolResult.ok(table_name=table_name, query=query, results=results)

            return ToolResult.fail(f"Unknown action '{action}'. Use 'enable' or 'search'.")
        except GenericDataMCPError as e:
            return ToolResult.fail(str(e))
