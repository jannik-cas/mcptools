"""Server introspection — connect to an MCP server and list its capabilities."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from mcptools.handshake import McpInitError, emit_error, mcp_initialize
from mcptools.jsonrpc import IdGenerator, make_request
from mcptools.proxy.transport import StdioTransport

console = Console()

_ids = IdGenerator()


async def inspect_server(
    command: list[str],
    timeout: int = 10,
    json_output: bool = False,
) -> None:
    """Connect to an MCP server and display its capabilities.

    Starts the server subprocess, performs the MCP handshake, then
    queries and displays tools, resources, and prompts.

    Args:
        command: Server command and arguments (e.g. ``["npx", "server"]``).
        timeout: Seconds to wait for each server response.
        json_output: If *True*, emit all output as a single JSON object.
    """
    transport = StdioTransport(command=command)

    try:
        await transport.start()
    except FileNotFoundError:
        emit_error(f"Command not found: {command[0]}", json_output)
        return
    except Exception as e:
        emit_error(f"Failed to start server: {e}", json_output)
        return

    result: dict[str, Any] = {}

    try:
        init_result = await mcp_initialize(transport, timeout, ids=_ids)

        server_info = init_result.get("serverInfo", {})
        capabilities = init_result.get("capabilities", {})

        server_name = server_info.get("name", "Unknown")
        server_version = server_info.get("version", "?")

        if json_output:
            result["server"] = {"name": server_name, "version": server_version}
        else:
            console.print(
                Panel(
                    f"[bold]{server_name}[/bold] v{server_version}",
                    title="MCP Server",
                    border_style="blue",
                )
            )

        # List tools
        if "tools" in capabilities:
            tools = await _fetch_capability(transport, "tools/list", "tools", timeout)
            if json_output:
                result["tools"] = tools
            else:
                _print_tools(tools)

        # List resources
        if "resources" in capabilities:
            resources = await _fetch_capability(transport, "resources/list", "resources", timeout)
            if json_output:
                result["resources"] = resources
            else:
                _print_resources(resources)

        # List prompts
        if "prompts" in capabilities:
            prompts = await _fetch_capability(transport, "prompts/list", "prompts", timeout)
            if json_output:
                result["prompts"] = prompts
            else:
                _print_prompts(prompts)

        if not capabilities:
            if json_output:
                result["warning"] = "Server reported no capabilities."
            else:
                console.print("[yellow]Server reported no capabilities.[/yellow]")

        if json_output:
            print(json.dumps(result, indent=2))

    except McpInitError as e:
        emit_error(str(e), json_output)
    except asyncio.TimeoutError:
        emit_error("Server timed out. Try increasing --timeout.", json_output)
    except json.JSONDecodeError as e:
        emit_error(f"Invalid JSON from server: {e}", json_output)
    except (ConnectionResetError, BrokenPipeError):
        emit_error("Server closed connection unexpectedly.", json_output)
    finally:
        await transport.stop()


async def _fetch_capability(
    transport: StdioTransport,
    method: str,
    result_key: str,
    timeout: int,
) -> list[dict[str, Any]]:
    """Fetch a list capability from the server.

    Args:
        transport: Active server transport.
        method: JSON-RPC method name (e.g. ``"tools/list"``).
        result_key: Key inside the result object (e.g. ``"tools"``).
        timeout: Seconds to wait for the response.

    Returns:
        List of capability items, or an empty list on error.
    """
    msg = make_request(method, msg_id=_ids.next())
    await transport.send(msg)
    response = await asyncio.wait_for(transport.receive(), timeout=timeout)
    if response is None or "error" in response:
        return []
    return response.get("result", {}).get(result_key, [])


def _print_tools(tools: list[dict[str, Any]]) -> None:
    if not tools:
        console.print("[dim]No tools available.[/dim]")
        return

    table = Table(title=f"Tools ({len(tools)})", border_style="blue")
    table.add_column("Name", style="bold cyan")
    table.add_column("Description")
    table.add_column("Parameters", style="dim")

    for tool in tools:
        name = tool.get("name", "?")
        desc = tool.get("description", "")
        schema = tool.get("inputSchema", {})
        params = _format_params(schema)
        table.add_row(name, desc, params)

    console.print(table)


def _print_resources(resources: list[dict[str, Any]]) -> None:
    if not resources:
        console.print("[dim]No resources available.[/dim]")
        return

    table = Table(title=f"Resources ({len(resources)})", border_style="green")
    table.add_column("URI", style="bold green")
    table.add_column("Name")
    table.add_column("MIME Type", style="dim")

    for res in resources:
        uri = res.get("uri", "?")
        name = res.get("name", "")
        mime = res.get("mimeType", "")
        table.add_row(uri, name, mime)

    console.print(table)


def _print_prompts(prompts: list[dict[str, Any]]) -> None:
    if not prompts:
        console.print("[dim]No prompts available.[/dim]")
        return

    table = Table(title=f"Prompts ({len(prompts)})", border_style="magenta")
    table.add_column("Name", style="bold magenta")
    table.add_column("Description")
    table.add_column("Arguments", style="dim")

    for prompt in prompts:
        name = prompt.get("name", "?")
        desc = prompt.get("description", "")
        args = prompt.get("arguments", [])
        args_str = ", ".join(
            f"{a.get('name', '?')}{'*' if a.get('required') else ''}" for a in args
        )
        table.add_row(name, desc, args_str)

    console.print(table)


def _format_params(schema: dict[str, Any]) -> str:
    """Format JSON Schema parameters into a readable string."""
    props = schema.get("properties", {})
    required = set(schema.get("required", []))

    if not props:
        return "(none)"

    parts = []
    for name, prop in props.items():
        ptype = prop.get("type", "any")
        suffix = "*" if name in required else ""
        parts.append(f"{name}: {ptype}{suffix}")

    return ", ".join(parts)
