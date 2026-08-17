from __future__ import annotations

import asyncio
import json

from mcp import types
from mcp.server import ServerRequestContext
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

from src.app import build_registry
from src.config import Config
from src.tools import ToolRegistry

_SERVER_NAME = "generic-data-mcp"
_SERVER_VERSION = "0.1.0"


class MCPServer:
    """Wires the dependency graph and exposes it over the MCP stdio transport.

    This is the only module that knows about the MCP protocol — tool classes
    under src/tools/ know nothing about it. Requests are delegated straight
    to the ToolRegistry.
    """

    def __init__(self, config: Config):
        self._registry = self._build_registry(config)
        self._server = Server(
            _SERVER_NAME,
            version=_SERVER_VERSION,
            on_list_tools=self._list_tools,
            on_call_tool=self._call_tool,
        )

    @staticmethod
    def _build_registry(config: Config) -> ToolRegistry:
        return build_registry(config)

    async def _list_tools(
        self,
        ctx: ServerRequestContext,
        params: types.PaginatedRequestParams | None,
    ) -> types.ListToolsResult:
        return types.ListToolsResult(
            tools=[
                types.Tool(
                    name=tool.name,
                    description=tool.description,
                    input_schema=tool.input_schema,
                )
                for tool in self._registry.list_tools()
            ]
        )

    async def _call_tool(
        self,
        ctx: ServerRequestContext,
        params: types.CallToolRequestParams,
    ) -> types.CallToolResult:
        result = self._registry.call(params.name, params.arguments or {})
        return types.CallToolResult(
            content=[types.TextContent(type="text", text=json.dumps(result.to_dict()))],
            is_error=not result.success,
        )

    async def run_stdio(self) -> None:
        async with stdio_server() as (read_stream, write_stream):
            await self._server.run(
                read_stream, write_stream, self._server.create_initialization_options()
            )


def main() -> None:
    config = Config.from_env()
    server = MCPServer(config)
    asyncio.run(server.run_stdio())


if __name__ == "__main__":
    main()
