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


async def inspect_server(command: list[str], timeout: int = 10) -> None:
    """Connect to an MCP server and display its capabilities."""
    transport = StdioTransport(command=command)

    try:
        await transport.start()
    except FileNotFoundError:
        console.print(f"[red]Command not found:[/red] {command[0]}")
        return
    except Exception as e:
        console.print(f"[red]Failed to start server:[/red] {e}")
        return

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
            console.print("[red]Server closed connection during initialization.[/red]")
            return

        if "error" in init_response:
            console.print(f"[red]Initialization error:[/red] {init_response['error']}")
            return

        server_info = init_response.get("result", {}).get("serverInfo", {})
        capabilities = init_response.get("result", {}).get("capabilities", {})

        # Send initialized notification
        await transport.send(make_request("notifications/initialized"))

        # Print server info
        server_name = server_info.get("name", "Unknown")
        server_version = server_info.get("version", "?")
        console.print(
            Panel(
                f"[bold]{server_name}[/bold] v{server_version}",
                title="MCP Server",
                border_style="blue",
            )
        )

        # List tools
        if "tools" in capabilities:
            await _list_tools(transport, timeout)

        # List resources
        if "resources" in capabilities:
            await _list_resources(transport, timeout)

        # List prompts
        if "prompts" in capabilities:
            await _list_prompts(transport, timeout)

        if not capabilities:
            console.print("[yellow]Server reported no capabilities.[/yellow]")

    except asyncio.TimeoutError:
        console.print("[red]Server timed out. Try increasing --timeout.[/red]")
    except json.JSONDecodeError as e:
        console.print(f"[red]Invalid JSON from server:[/red] {e}")
    except (ConnectionResetError, BrokenPipeError):
        console.print("[red]Server closed connection unexpectedly.[/red]")
    finally:
        await transport.stop()


async def _list_tools(transport: StdioTransport, timeout: int) -> None:
    """List all tools from the server."""
    msg = make_request("tools/list", msg_id=_ids.next())
    await transport.send(msg)
    response = await asyncio.wait_for(transport.receive(), timeout=timeout)

    if response is None or "error" in response:
        console.print("[red]Failed to list tools.[/red]")
        return

    tools = response.get("result", {}).get("tools", [])

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


async def _list_resources(transport: StdioTransport, timeout: int) -> None:
    """List all resources from the server."""
    msg = make_request("resources/list", msg_id=_ids.next())
    await transport.send(msg)
    response = await asyncio.wait_for(transport.receive(), timeout=timeout)

    if response is None or "error" in response:
        console.print("[red]Failed to list resources.[/red]")
        return

    resources = response.get("result", {}).get("resources", [])

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


async def _list_prompts(transport: StdioTransport, timeout: int) -> None:
    """List all prompts from the server."""
    msg = make_request("prompts/list", msg_id=_ids.next())
    await transport.send(msg)
    response = await asyncio.wait_for(transport.receive(), timeout=timeout)

    if response is None or "error" in response:
        console.print("[red]Failed to list prompts.[/red]")
        return

    prompts = response.get("result", {}).get("prompts", [])

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
