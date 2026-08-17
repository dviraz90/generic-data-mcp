"""Local web GUI (ingestion console) transport for generic-data-mcp.

A Flask app that reuses the exact same ToolRegistry as the MCP stdio server,
exposing upload/list/describe/query over HTTP for a browser-based console.
"""

from src.webui.server import create_app, main

__all__ = ["create_app", "main"]
