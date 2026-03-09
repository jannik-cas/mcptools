"""Tool caller — connect to an MCP server and invoke a specific tool."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax

from mcptools.handshake import McpInitError, emit_error, mcp_initialize
from mcptools.jsonrpc import IdGenerator, make_request
from mcptools.proxy.transport import StdioTransport

console = Console()

_ids = IdGenerator()


async def call_tool(
    command: list[str],
    tool_name: str,
    arguments: dict[str, Any] | None = None,
    timeout: int = 30,
    json_output: bool = False,
) -> None:
    """Connect to an MCP server, call a tool, and print the result.

    Performs the MCP handshake, verifies the requested tool exists,
    invokes it with the provided arguments, and displays the response.

    Args:
        command: Server command and arguments.
        tool_name: Name of the tool to invoke.
        arguments: Optional dict of tool arguments.
        timeout: Seconds to wait for each server response.
        json_output: If *True*, emit output as JSON.
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

    try:
        init_result = await mcp_initialize(transport, timeout, ids=_ids)

        # Check capabilities — verify server has tools
        capabilities = init_result.get("capabilities", {})
        if "tools" not in capabilities:
            emit_error("Server does not expose any tools.", json_output)
            return

        # List tools to verify the requested one exists
        await transport.send(make_request("tools/list", msg_id=_ids.next()))
        tools_response = await asyncio.wait_for(transport.receive(), timeout=timeout)

        if tools_response is None or "error" in tools_response:
            emit_error("Failed to list tools.", json_output)
            return

        tools = tools_response.get("result", {}).get("tools", [])
        tool_names = [t.get("name") for t in tools]

        if tool_name not in tool_names:
            if json_output:
                print(
                    json.dumps(
                        {
                            "error": f"Tool '{tool_name}' not found",
                            "available_tools": tool_names,
                        }
                    )
                )
            else:
                console.print(f"[red]Tool '{tool_name}' not found.[/red]")
                console.print(f"[dim]Available: {', '.join(tool_names)}[/dim]")
            return

        # Call the tool
        call_params: dict[str, Any] = {"name": tool_name}
        if arguments:
            call_params["arguments"] = arguments

        await transport.send(make_request("tools/call", call_params, msg_id=_ids.next()))
        call_response = await asyncio.wait_for(transport.receive(), timeout=timeout)

        if call_response is None:
            emit_error("Server closed connection during tool call.", json_output)
            return

        if "error" in call_response:
            err = call_response["error"]
            msg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
            emit_error(f"Tool error: {msg}", json_output)
            return

        result = call_response.get("result", {})

        if json_output:
            print(json.dumps(result, indent=2))
        else:
            _print_result(tool_name, result)

    except McpInitError as e:
        emit_error(str(e), json_output)
    except asyncio.TimeoutError:
        emit_error(f"Timed out after {timeout}s.", json_output)
    except json.JSONDecodeError as e:
        emit_error(f"Invalid JSON from server: {e}", json_output)
    except (ConnectionResetError, BrokenPipeError):
        emit_error("Server closed connection unexpectedly.", json_output)
    finally:
        await transport.stop()


def _print_result(tool_name: str, result: dict[str, Any]) -> None:
    """Pretty-print a tool call result."""
    content = result.get("content", [])

    if not content:
        console.print("[dim]Tool returned empty result.[/dim]")
        return

    for item in content:
        item_type = item.get("type", "text")

        if item_type == "text":
            text = item.get("text", "")
            # If it looks like JSON, syntax-highlight it
            try:
                parsed = json.loads(text)
                formatted = json.dumps(parsed, indent=2)
                console.print(
                    Panel(
                        Syntax(formatted, "json", theme="monokai", line_numbers=False),
                        title=f"[bold]{tool_name}[/bold]",
                        border_style="green",
                    )
                )
            except (json.JSONDecodeError, ValueError):
                # Plain text — just print it
                if len(text) > 200:
                    console.print(
                        Panel(
                            text,
                            title=f"[bold]{tool_name}[/bold]",
                            border_style="green",
                        )
                    )
                else:
                    console.print(f"[green]{tool_name}:[/green] {text}")

        elif item_type == "image":
            mime = item.get("mimeType", "image/*")
            console.print(f"[dim](image: {mime}, {len(item.get('data', ''))} bytes)[/dim]")

        elif item_type == "resource":
            uri = item.get("resource", {}).get("uri", "?")
            console.print(f"[dim](resource: {uri})[/dim]")
