from __future__ import annotations

from src.config import Config
from src.parsers.registry import ParserRegistry
from src.storage.sqlite_store import SQLiteStore
from src.tools import (
    DescribeTableTool,
    IngestFileTool,
    ListDatasetsTool,
    QueryTool,
    SearchTool,
    ToolRegistry,
)
from src.validators.path import PathValidator


def build_registry(config: Config) -> ToolRegistry:
    """Wire the dependency graph and return the ToolRegistry.

    Shared by every transport (MCP stdio in server.py, HTTP in webui/server.py)
    so both expose the exact same five tools over the same storage layer.
    """
    store = SQLiteStore(config.db_path)
    path_validator = PathValidator(config.allowed_dirs)
    parser_registry = ParserRegistry()

    return ToolRegistry(
        [
            IngestFileTool(store, path_validator, parser_registry),
            ListDatasetsTool(store),
            DescribeTableTool(store),
            QueryTool(store),
            SearchTool(store),
        ]
    )
