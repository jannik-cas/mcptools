"""Parse MCP configuration files from various IDEs."""

from __future__ import annotations

import json
import os
from pathlib import Path

from pydantic import BaseModel, Field


class ServerConfig(BaseModel):
    """Configuration for a single MCP server."""

    name: str
    command: str
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    url: str | None = None
    transport: str = "stdio"  # "stdio" or "sse"


class McpConfig(BaseModel):
    """Parsed MCP configuration with all servers."""

    servers: dict[str, ServerConfig] = Field(default_factory=dict)
    source_path: Path | None = None


# Known config file locations per IDE
CONFIG_LOCATIONS: list[tuple[str, Path]] = [
    ("Claude Desktop", Path.home() / ".claude" / "claude_desktop_config.json"),
    (
        "Claude Desktop (macOS)",
        Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json",
    ),
    ("Cursor", Path.home() / ".cursor" / "mcp.json"),
    ("VS Code", Path.home() / ".vscode" / "mcp.json"),
    ("Windsurf", Path.home() / ".codeium" / "windsurf" / "mcp_config.json"),
]


def find_config() -> Path | None:
    """Auto-detect MCP config file from known IDE locations."""
    for _name, path in CONFIG_LOCATIONS:
        if path.exists():
            return path
    return None


def parse_config(config_path: Path) -> McpConfig:
    """Parse an MCP config file into a structured McpConfig."""
    with open(config_path) as f:
        raw = json.load(f)

    servers: dict[str, ServerConfig] = {}

    # Handle both top-level "mcpServers" and nested structures
    servers_raw = raw.get("mcpServers", raw.get("servers", raw))

    if isinstance(servers_raw, dict):
        for name, server_data in servers_raw.items():
            if not isinstance(server_data, dict):
                continue

            # Resolve environment variables in env
            env = {}
            for k, v in server_data.get("env", {}).items():
                if isinstance(v, str) and v.startswith("${") and v.endswith("}"):
                    env_var = v[2:-1]
                    env[k] = os.environ.get(env_var, v)
                else:
                    env[k] = str(v)

            # Determine transport type
            url = server_data.get("url")
            transport = "sse" if url else "stdio"

            servers[name] = ServerConfig(
                name=name,
                command=server_data.get("command", ""),
                args=server_data.get("args", []),
                env=env,
                url=url,
                transport=transport,
            )

    return McpConfig(servers=servers, source_path=config_path)


def load_config(config_path: Path | None = None) -> McpConfig:
    """Load MCP config — from explicit path or auto-detected."""
    if config_path is None:
        config_path = find_config()

    if config_path is None:
        return McpConfig()

    return parse_config(config_path)
