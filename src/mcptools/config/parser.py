"""Parse MCP configuration files from various IDEs.

Detects and loads MCP server configurations from known IDE config
locations (Claude Desktop, Cursor, VS Code, Windsurf) or from an
explicit file path.  Environment variables in ``${VAR}`` format are
resolved from the current environment at parse time.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from pydantic import BaseModel, Field
from rich.console import Console

console = Console(stderr=True)


class ServerConfig(BaseModel):
    """Configuration for a single MCP server.

    Attributes:
        name: Human-readable server name (usually the config key).
        command: Executable to run (e.g. ``"npx"``).
        args: Command-line arguments passed after *command*.
        env: Environment variables injected into the server process.
        url: SSE endpoint URL, if using SSE transport.
        transport: ``"stdio"`` (default) or ``"sse"``.
    """

    name: str
    command: str
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    url: str | None = None
    transport: str = "stdio"  # "stdio" or "sse"


class McpConfig(BaseModel):
    """Parsed MCP configuration with all servers.

    Attributes:
        servers: Mapping of server name to its ``ServerConfig``.
        source_path: Filesystem path the configuration was loaded from.
    """

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
    """Auto-detect an MCP config file from known IDE locations.

    Searches ``CONFIG_LOCATIONS`` in order and returns the first path
    that exists on disk, or *None* if no config file is found.

    Returns:
        Path to the first detected config file, or *None*.
    """
    for _name, path in CONFIG_LOCATIONS:
        if path.exists():
            return path
    return None


def parse_config(config_path: Path) -> McpConfig:
    """Parse an MCP config file into a structured ``McpConfig``.

    Supports both ``mcpServers`` (Claude Desktop style) and ``servers``
    top-level keys.  Environment variable references (``${VAR}``) in the
    ``env`` block are resolved against ``os.environ``.

    Args:
        config_path: Path to the JSON config file.

    Returns:
        Parsed ``McpConfig`` with all discovered servers.
    """
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
    """Load MCP config — from an explicit path or auto-detected.

    Args:
        config_path: Explicit path to a config file.  If *None*, calls
            :func:`find_config` to auto-detect.

    Returns:
        Parsed ``McpConfig``, or an empty config if no file is found.
    """
    if config_path is None:
        config_path = find_config()

    if config_path is None:
        return McpConfig()

    return parse_config(config_path)


def select_server(
    config: McpConfig,
    server_name: str | None = None,
) -> ServerConfig | None:
    """Select a server from the configuration.

    When *server_name* is given, looks it up directly.  When only one
    server is configured, auto-selects it.  When multiple servers exist
    and no name is provided, prints the available options and returns
    *None*.

    Args:
        config: Parsed MCP configuration.
        server_name: Optional server name to look up.

    Returns:
        The selected ``ServerConfig``, or *None* if selection failed.
    """
    if not config.servers:
        console.print("[red]No MCP servers found in config.[/red]")
        return None

    if server_name:
        if server_name not in config.servers:
            console.print(f"[red]Server '{server_name}' not found in config.[/red]")
            console.print(f"Available: {', '.join(config.servers.keys())}")
            return None
        return config.servers[server_name]

    if len(config.servers) == 1:
        return next(iter(config.servers.values()))

    console.print("[yellow]Multiple servers found. Use --server to select one:[/yellow]")
    for name in config.servers:
        console.print(f"  - {name}")
    return None
