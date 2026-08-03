from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolResult:
    """Uniform envelope every tool returns.

    `ok` wraps a success payload; `fail` carries a message written for LLM
    recovery (what to do next), not just "invalid input".
    """

    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    @classmethod
    def ok(cls, **data: Any) -> "ToolResult":
        return cls(success=True, data=data)

    @classmethod
    def fail(cls, error: str) -> "ToolResult":
        return cls(success=False, error=error)

    def to_dict(self) -> dict[str, Any]:
        if self.success:
            return {"success": True, **self.data}
        return {"success": False, "error": self.error}


class BaseTool(ABC):
    """Command object exposing one MCP tool. Knows nothing about the MCP protocol."""

    name: str
    description: str
    input_schema: dict[str, Any]

    @abstractmethod
    def execute(self, arguments: dict[str, Any]) -> ToolResult:
        raise NotImplementedError


class ToolRegistry:
    """Holds every BaseTool and dispatches calls by name."""

    def __init__(self, tools: list[BaseTool]):
        self._tools: dict[str, BaseTool] = {tool.name: tool for tool in tools}

    def list_tools(self) -> list[BaseTool]:
        return list(self._tools.values())

    def call(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        tool = self._tools.get(name)
        if tool is None:
            available = ", ".join(sorted(self._tools))
            return ToolResult.fail(f"Unknown tool '{name}'. Available tools: {available}.")
        try:
            return tool.execute(arguments)
        except Exception as e:
            return ToolResult.fail(f"{type(e).__name__}: {e}")
