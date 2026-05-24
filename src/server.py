import asyncio

import mcp.server.stdio
from mcp import types
from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions

from . import config
from .embeddings.http import HttpEmbedder
from .parsers.registry import ParserRegistry
from .storage.sqlite_store import SQLiteStore
from .tools.base import ToolRegistry
from .tools.describe_table import DescribeTableTool
from .tools.ingest_file import IngestFileTool
from .tools.list_datasets import ListDatasetsTool
from .tools.query import QueryTool
from .tools.search import SearchTool
from .tools.vector_search import VectorSearchTool
from .validators.path import PathValidator


def _build_registry(store: SQLiteStore, path_validator: PathValidator) -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(IngestFileTool(store, ParserRegistry(), path_validator))
    registry.register(ListDatasetsTool(store))
    registry.register(DescribeTableTool(store))
    registry.register(QueryTool(store))
    registry.register(SearchTool(store))
    registry.register(VectorSearchTool(store))
    return registry


def main() -> None:
    embedder = None
    if config.EMBED_API_KEY or config.EMBED_URL != "https://api.openai.com/v1/embeddings":
        embedder = HttpEmbedder(config.EMBED_URL, config.EMBED_MODEL, config.EMBED_API_KEY)

    store = SQLiteStore(config.DB_PATH, embedder)
    path_validator = PathValidator(config.ALLOWED_DIRS)
    registry = _build_registry(store, path_validator)

    server = Server("generic-data-mcp")

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        return [
            types.Tool(
                name=t.name,
                description=t.description,
                inputSchema=t.input_schema,
            )
            for t in registry.all_tools()
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
        tool = registry.get(name)
        if tool is None:
            return [types.TextContent(type="text", text=f"Unknown tool '{name}'.")]
        result = tool.run(**(arguments or {}))
        return [types.TextContent(type="text", text=result.content)]

    async def run() -> None:
        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="generic-data-mcp",
                    server_version="0.1.0",
                    capabilities=server.get_capabilities(
                        notification_options=NotificationOptions(),
                        experimental_capabilities={},
                    ),
                ),
            )

    asyncio.run(run())
