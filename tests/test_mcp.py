"""Tests for optional MCP server integration."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from r_cli.core.config import Config, MCPServerConfig
from r_cli.mcp_client import MCPClient


def mcp_config(tmp_path: Path, script: Path) -> Config:
    config = Config(
        home_dir=str(tmp_path),
        output_dir=str(tmp_path / "output"),
        skills_dir=str(tmp_path / "skills"),
    )
    config.mcp.servers["test"] = MCPServerConfig(
        command=str(Path(__import__("sys").executable)),
        args=[str(script)],
        timeout_seconds=10,
    )
    return config


def test_mcp_server_config_round_trip(tmp_path: Path):
    config = Config()
    config.mcp.servers["demo"] = MCPServerConfig(
        command="uvx",
        args=["demo-server"],
        env={"MODE": "test"},
    )
    path = tmp_path / "config.yaml"

    config.save(str(path))
    loaded = Config.load(str(path))

    assert loaded.mcp.servers["demo"].command == "uvx"
    assert loaded.mcp.servers["demo"].args == ["demo-server"]
    assert loaded.mcp.servers["demo"].env == {"MODE": "test"}


def test_mcp_environment_references_are_resolved():
    with patch.dict(os.environ, {"PRIVATE_TOKEN": "secret-value"}):
        result = MCPClient.resolve_environment({"API_TOKEN": "${PRIVATE_TOKEN}", "MODE": "test"})

    assert result == {"API_TOKEN": "secret-value", "MODE": "test"}


def test_mcp_stdio_discovery_and_call(tmp_path: Path):
    pytest.importorskip("mcp")
    script = tmp_path / "server.py"
    script.write_text(
        """
from mcp.server.fastmcp import FastMCP

server = FastMCP("test")

@server.tool()
def add(a: int, b: int) -> int:
    return a + b

if __name__ == "__main__":
    server.run(transport="stdio")
""".strip()
    )
    client = MCPClient(mcp_config(tmp_path, script))

    tools = client.list_tools("test")
    result = client.call_tool("test", "add", {"a": 2, "b": 3}, auto_approve=True)

    assert [tool.name for tool in tools] == ["add"]
    assert result == {"result": 5}
