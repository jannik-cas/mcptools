"""CLI entry point for mcptools."""

from __future__ import annotations

import asyncio
from pathlib import Path

import click
from rich.console import Console

console = Console()


@click.group()
@click.version_option(package_name="mcptools")
@click.option("-v", "--verbose", is_flag=True, help="Print raw JSON-RPC messages to stderr.")
@click.pass_context
def cli(ctx: click.Context, verbose: bool) -> None:
    """mcptools — mitmproxy for MCP.

    Intercept, inspect, debug, and replay MCP server traffic.
    """
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose


@cli.command()
@click.argument("server_command", nargs=-1, required=True)
@click.option("--timeout", "-t", default=10, help="Connection timeout in seconds.")
def inspect(server_command: tuple[str, ...], timeout: int) -> None:
    """Inspect an MCP server — list tools, resources, and prompts.

    Examples:

        mcptools inspect python my_server.py

        mcptools inspect uvx my-mcp-server

        mcptools inspect npx @modelcontextprotocol/server-filesystem /tmp
    """
    from mcptools.inspect.server import inspect_server

    asyncio.run(inspect_server(list(server_command), timeout=timeout))


@cli.command()
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True, path_type=Path),
    help="Path to MCP config file (e.g. claude_desktop_config.json).",
)
@click.option(
    "--server",
    "-s",
    multiple=True,
    help="Specific server name(s) to check. If omitted, checks all.",
)
@click.option("--timeout", "-t", default=10, help="Connection timeout in seconds.")
def doctor(config: Path | None, server: tuple[str, ...], timeout: int) -> None:
    """Diagnose MCP server configuration and connectivity issues.

    Without --config, auto-detects config from known IDE locations.
    """
    from mcptools.doctor.checks import run_doctor

    asyncio.run(run_doctor(config_path=config, server_names=list(server), timeout=timeout))


@cli.command()
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True, path_type=Path),
    help="Path to MCP config file.",
)
@click.option("--port", "-p", default=0, help="SSE proxy port (0 = stdio only).")
@click.option("--server", "-s", help="Server name from config to proxy.")
@click.option("--tui/--no-tui", default=True, help="Show TUI dashboard.")
def proxy(config: Path | None, port: int, server: str | None, tui: bool) -> None:
    """Start the MCP proxy — intercept traffic between IDE and MCP server.

    Sits between your IDE and MCP servers, capturing all tool calls,
    resources, and prompts flowing through.
    """
    from mcptools.proxy.interceptor import run_proxy

    asyncio.run(run_proxy(config_path=config, port=port, server_name=server, use_tui=tui))


@cli.command()
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True, path_type=Path),
    help="Path to MCP config file.",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    default="session.json",
    help="Output file for recorded session.",
)
@click.option("--server", "-s", help="Server name from config to record.")
def record(config: Path | None, output: Path, server: str | None) -> None:
    """Record an MCP session to a JSON file for later replay.

    Starts the proxy in recording mode — all MCP messages are saved.
    """
    from mcptools.record.recorder import run_recorder

    asyncio.run(run_recorder(config_path=config, output_path=output, server_name=server))


@cli.command()
@click.argument("session_file", type=click.Path(exists=True, path_type=Path))
@click.option("--speed", default=1.0, help="Replay speed multiplier.")
@click.option("--filter", "filter_method", help="Filter by method name (supports wildcards).")
def replay(session_file: Path, speed: float, filter_method: str | None) -> None:
    """Replay a recorded MCP session.

    Useful for debugging — replay previous sessions to reproduce issues.
    """
    from mcptools.record.replayer import run_replayer

    asyncio.run(run_replayer(session_path=session_file, speed=speed, filter_method=filter_method))


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
