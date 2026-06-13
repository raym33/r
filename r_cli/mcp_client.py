"""Optional Model Context Protocol client integration."""

from __future__ import annotations

import asyncio
import os
import re
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from r_cli.core.config import Config, MCPServerConfig
from r_cli.core.llm import Tool
from r_cli.core.permissions import ApprovalCallback, PermissionManager


class MCPError(RuntimeError):
    """Raised when an MCP server cannot be used."""


@dataclass
class MCPToolInfo:
    """Serializable MCP tool metadata."""

    name: str
    description: str
    input_schema: dict[str, Any]


def _sdk():
    try:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
    except ImportError as exc:
        raise MCPError("MCP support is not installed. Run: pip install 'r-cli-ai[mcp]'") from exc
    return ClientSession, StdioServerParameters, stdio_client


class MCPClient:
    """Connect to configured MCP servers over stdio."""

    def __init__(self, config: Config | None = None):
        self.config = config or Config.load()

    def get_server(self, server_name: str) -> MCPServerConfig:
        server = self.config.mcp.servers.get(server_name)
        if server is None:
            raise MCPError(f"Unknown MCP server: {server_name}")
        if not server.enabled:
            raise MCPError(f"MCP server is disabled: {server_name}")
        return server

    @staticmethod
    def resolve_environment(environment: dict[str, str]) -> dict[str, str]:
        """Resolve $VAR and ${VAR} references without storing secrets in YAML."""
        resolved = {}
        for key, value in environment.items():
            match = re.fullmatch(
                r"\$(?:\{([A-Za-z_][A-Za-z0-9_]*)\}|([A-Za-z_][A-Za-z0-9_]*))", value
            )
            if match:
                variable = match.group(1) or match.group(2)
                if variable not in os.environ:
                    raise MCPError(f"Environment variable is not set: {variable}")
                resolved[key] = os.environ[variable]
            else:
                resolved[key] = value
        return resolved

    async def list_tools_async(self, server_name: str) -> list[MCPToolInfo]:
        client_session_class, server_parameters_class, stdio_client = _sdk()
        server = self.get_server(server_name)
        parameters = server_parameters_class(
            command=server.command,
            args=server.args,
            env=self.resolve_environment(server.env) or None,
            cwd=server.cwd,
        )

        try:
            async with asyncio.timeout(server.timeout_seconds):
                async with stdio_client(parameters) as (read, write):
                    async with client_session_class(read, write) as session:
                        await session.initialize()
                        result = await session.list_tools()
        except TimeoutError as exc:
            raise MCPError(f"MCP server '{server_name}' timed out") from exc
        except Exception as exc:
            raise MCPError(f"MCP server '{server_name}' failed: {exc}") from exc

        return [
            MCPToolInfo(
                name=tool.name,
                description=tool.description or "",
                input_schema=tool.inputSchema,
            )
            for tool in result.tools
        ]

    async def call_tool_async(
        self,
        server_name: str,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> Any:
        client_session_class, server_parameters_class, stdio_client = _sdk()
        server = self.get_server(server_name)
        parameters = server_parameters_class(
            command=server.command,
            args=server.args,
            env=self.resolve_environment(server.env) or None,
            cwd=server.cwd,
        )

        try:
            async with asyncio.timeout(server.timeout_seconds):
                async with stdio_client(parameters) as (read, write):
                    async with client_session_class(read, write) as session:
                        await session.initialize()
                        result = await session.call_tool(
                            tool_name,
                            arguments,
                            read_timeout_seconds=timedelta(seconds=server.timeout_seconds),
                        )
        except TimeoutError as exc:
            raise MCPError(f"MCP tool '{server_name}.{tool_name}' timed out") from exc
        except Exception as exc:
            raise MCPError(f"MCP tool '{server_name}.{tool_name}' failed: {exc}") from exc

        if result.isError:
            raise MCPError(f"MCP tool '{server_name}.{tool_name}' returned an error")
        if result.structuredContent is not None:
            return result.structuredContent

        content = []
        for item in result.content:
            if hasattr(item, "text"):
                content.append(item.text)
            elif hasattr(item, "model_dump"):
                content.append(item.model_dump(mode="json"))
            else:
                content.append(str(item))
        return content[0] if len(content) == 1 else content

    def list_tools(self, server_name: str) -> list[MCPToolInfo]:
        return asyncio.run(self.list_tools_async(server_name))

    def call_tool(
        self,
        server_name: str,
        tool_name: str,
        arguments: dict[str, Any],
        approval_callback: ApprovalCallback | None = None,
        auto_approve: bool = False,
    ) -> Any:
        permissions = PermissionManager(
            self.config,
            approval_callback=approval_callback,
            auto_approve=auto_approve,
            source=f"mcp:{server_name}",
        )
        return permissions.execute(
            f"mcp:{server_name}",
            tool_name,
            lambda **kwargs: asyncio.run(self.call_tool_async(server_name, tool_name, kwargs)),
            arguments,
        )

    def as_r_tools(
        self,
        server_name: str,
        approval_callback: ApprovalCallback | None = None,
        auto_approve: bool = False,
    ) -> list[Tool]:
        """Expose one MCP server's tools through R's native Tool model."""
        tools = []
        safe_server_name = re.sub(r"[^a-zA-Z0-9_-]", "_", server_name)
        for info in self.list_tools(server_name):
            original_name = info.name

            def handler(_tool_name=original_name, **kwargs):
                return self.call_tool(
                    server_name,
                    _tool_name,
                    kwargs,
                    approval_callback=approval_callback,
                    auto_approve=auto_approve,
                )

            tools.append(
                Tool(
                    name=f"mcp_{safe_server_name}_{original_name}",
                    description=f"[MCP:{server_name}] {info.description}",
                    parameters=info.input_schema,
                    handler=handler,
                )
            )
        return tools
