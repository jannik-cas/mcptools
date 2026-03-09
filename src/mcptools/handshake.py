"""Shared MCP handshake logic — initialize connection with an MCP server.

Centralises the initialize/initialized handshake that was previously
duplicated in inspect, caller, and doctor modules.  Uses the package
``__version__`` so the advertised client version stays in sync with
the installed release.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from rich.console import Console

import mcptools
from mcptools.jsonrpc import IdGenerator, make_request
from mcptools.proxy.transport import StdioTransport

console = Console()


class McpInitError(Exception):
    """Raised when the MCP initialize handshake fails."""


async def mcp_initialize(
    transport: StdioTransport,
    timeout: float = 10,
    *,
    ids: IdGenerator | None = None,
    client_name: str = "mcptools",
) -> dict[str, Any]:
    """Perform the MCP initialize handshake with a server process.

    Sends the ``initialize`` request, waits for the server's capability
    response, then sends the ``initialized`` notification.

    Args:
        transport: A started ``StdioTransport`` connected to the server.
        timeout: Seconds to wait for the server response.
        ids: Optional ``IdGenerator``; a fresh one is created if *None*.
        client_name: Client name advertised in the handshake.

    Returns:
        The full ``result`` dict from the server's initialize response,
        containing keys like ``serverInfo`` and ``capabilities``.

    Raises:
        McpInitError: If the server doesn't respond or returns an error.
    """
    if ids is None:
        ids = IdGenerator()

    init_msg = make_request(
        "initialize",
        {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": client_name, "version": mcptools.__version__},
        },
        msg_id=ids.next(),
    )
    await transport.send(init_msg)
    response = await asyncio.wait_for(transport.receive(), timeout=timeout)

    if response is None:
        raise McpInitError("Server closed connection during initialization.")

    if "error" in response:
        err = response["error"]
        detail = err.get("message", str(err)) if isinstance(err, dict) else str(err)
        raise McpInitError(f"Initialization error: {detail}")

    # Send initialized notification
    await transport.send(make_request("notifications/initialized"))

    return response.get("result", {})


def emit_error(message: str, json_output: bool = False) -> None:
    """Print an error to the terminal or as JSON.

    Provides a single implementation for the error-output pattern used
    across inspect, caller, and doctor modules.

    Args:
        message: The error message to display.
        json_output: If *True*, print a JSON object with an ``error`` key;
            otherwise print a Rich-formatted red message.
    """
    if json_output:
        print(json.dumps({"error": message}))
    else:
        console.print(f"[red]{message}[/red]")
