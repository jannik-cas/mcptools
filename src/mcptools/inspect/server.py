"""Server introspection — connect to an MCP server and list its capabilities."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from mcptools.jsonrpc import IdGenerator, make_request
from mcptools.proxy.transport import StdioTransport

console = Console()

_ids = IdGenerator()


async def inspect_server(
    command: list[str],
    timeout: int = 10,
    json_output: bool = False,
) -> None:
    """Connect to an MCP server and display its capabilities."""
    transport = StdioTransport(command=command)

    try:
        await transport.start()
    except FileNotFoundError:
        if json_output:
            print(json.dumps({"error": f"Command not found: {command[0]}"}))
        else:
            console.print(f"[red]Command not found:[/red] {command[0]}")
        return
    except Exception as e:
        if json_output:
            print(json.dumps({"error": f"Failed to start server: {e}"}))
        else:
            console.print(f"[red]Failed to start server:[/red] {e}")
        return

    result: dict[str, Any] = {}

    try:
        # Initialize
        init_msg = make_request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "mcptools", "version": "0.1.0"},
            },
            msg_id=_ids.next(),
        )
        await transport.send(init_msg)
        init_response = await asyncio.wait_for(transport.receive(), timeout=timeout)

        if init_response is None:
            _emit_error("Server closed connection during initialization.", json_output)
            return

        if "error" in init_response:
            _emit_error(f"Initialization error: {init_response['error']}", json_output)
            return

        server_info = init_response.get("result", {}).get("serverInfo", {})
        capabilities = init_response.get("result", {}).get("capabilities", {})

        # Send initialized notification
        await transport.send(make_request("notifications/initialized"))

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
            tools = await _fetch_tools(transport, timeout)
            if json_output:
                result["tools"] = tools
            else:
                _print_tools(tools)

        # List resources
        if "resources" in capabilities:
            resources = await _fetch_resources(transport, timeout)
            if json_output:
                result["resources"] = resources
            else:
                _print_resources(resources)

        # List prompts
        if "prompts" in capabilities:
            prompts = await _fetch_prompts(transport, timeout)
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

    except asyncio.TimeoutError:
        _emit_error("Server timed out. Try increasing --timeout.", json_output)
    except json.JSONDecodeError as e:
        _emit_error(f"Invalid JSON from server: {e}", json_output)
    except (ConnectionResetError, BrokenPipeError):
        _emit_error("Server closed connection unexpectedly.", json_output)
    finally:
        await transport.stop()


def _emit_error(msg: str, json_output: bool) -> None:
    if json_output:
        print(json.dumps({"error": msg}))
    else:
        console.print(f"[red]{msg}[/red]")


async def _fetch_tools(transport: StdioTransport, timeout: int) -> list[dict[str, Any]]:
    msg = make_request("tools/list", msg_id=_ids.next())
    await transport.send(msg)
    response = await asyncio.wait_for(transport.receive(), timeout=timeout)
    if response is None or "error" in response:
        return []
    return response.get("result", {}).get("tools", [])


async def _fetch_resources(transport: StdioTransport, timeout: int) -> list[dict[str, Any]]:
    msg = make_request("resources/list", msg_id=_ids.next())
    await transport.send(msg)
    response = await asyncio.wait_for(transport.receive(), timeout=timeout)
    if response is None or "error" in response:
        return []
    return response.get("result", {}).get("resources", [])


async def _fetch_prompts(transport: StdioTransport, timeout: int) -> list[dict[str, Any]]:
    msg = make_request("prompts/list", msg_id=_ids.next())
    await transport.send(msg)
    response = await asyncio.wait_for(transport.receive(), timeout=timeout)
    if response is None or "error" in response:
        return []
    return response.get("result", {}).get("prompts", [])


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
