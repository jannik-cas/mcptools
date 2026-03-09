"""Core proxy logic — intercepts and forwards MCP traffic."""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any, Callable

from rich.console import Console
from rich.table import Table
from rich.text import Text

from mcptools.config.parser import load_config, ServerConfig
from mcptools.proxy.transport import McpMessage, StdioTransport, StdinReader, StdoutWriter

console = Console(stderr=True)

# Type alias for message callbacks
MessageCallback = Callable[[McpMessage], None]


class ProxyInterceptor:
    """Intercepts MCP traffic between client and server."""

    def __init__(
        self,
        server_config: ServerConfig,
        on_message: MessageCallback | None = None,
    ) -> None:
        self.server_config = server_config
        self.on_message = on_message
        self.messages: list[McpMessage] = []
        self._pending_requests: dict[int | str, float] = {}  # id -> timestamp
        self._transport: StdioTransport | None = None

    async def start(self) -> None:
        """Start the proxy — read from stdin, forward to server, relay responses."""
        command = [self.server_config.command, *self.server_config.args]
        self._transport = StdioTransport(command=command, env=self.server_config.env)
        await self._transport.start()

        stdin_reader = StdinReader()
        await stdin_reader.start()
        stdout_writer = StdoutWriter()

        # Run client->server and server->client relays concurrently
        await asyncio.gather(
            self._relay_client_to_server(stdin_reader),
            self._relay_server_to_client(stdout_writer),
            self._drain_stderr(),
        )

    async def _relay_client_to_server(self, reader: StdinReader) -> None:
        """Read from client (stdin) and forward to server."""
        assert self._transport is not None

        while True:
            try:
                data = await reader.receive()
            except Exception:
                break
            if data is None:
                break

            msg = McpMessage(
                timestamp=time.time(),
                direction="client_to_server",
                data=data,
            )
            self._record(msg)

            # Track request start time
            if msg.msg_id is not None and msg.is_request:
                self._pending_requests[msg.msg_id] = msg.timestamp

            await self._transport.send(data)

    async def _relay_server_to_client(self, writer: StdoutWriter) -> None:
        """Read from server and forward to client (stdout)."""
        assert self._transport is not None

        while self._transport.is_running:
            try:
                data = await self._transport.receive()
            except Exception:
                break
            if data is None:
                break

            msg = McpMessage(
                timestamp=time.time(),
                direction="server_to_client",
                data=data,
            )

            # Calculate latency for responses
            if msg.msg_id is not None and msg.msg_id in self._pending_requests:
                start = self._pending_requests.pop(msg.msg_id)
                latency_ms = (msg.timestamp - start) * 1000
                msg.data["_latency_ms"] = round(latency_ms, 1)

            self._record(msg)
            writer.send_sync(data)

    async def _drain_stderr(self) -> None:
        """Drain stderr from the server process (log it)."""
        assert self._transport is not None

        while self._transport.is_running:
            line = await self._transport.read_stderr()
            if line is None:
                break
            console.print(f"[dim]server stderr:[/dim] {line}")

    def _record(self, msg: McpMessage) -> None:
        """Record a message and invoke callback."""
        self.messages.append(msg)
        if self.on_message:
            self.on_message(msg)

    async def stop(self) -> None:
        if self._transport:
            await self._transport.stop()


def _print_message(msg: McpMessage) -> None:
    """Default message printer for non-TUI mode."""
    arrow = ">>>" if msg.direction == "client_to_server" else "<<<"
    color = "cyan" if msg.direction == "client_to_server" else "green"

    if msg.is_error:
        color = "red"

    method = msg.method or "(response)"
    latency = ""
    if "_latency_ms" in msg.data:
        ms = msg.data["_latency_ms"]
        latency_color = "green" if ms < 500 else "yellow" if ms < 2000 else "red"
        latency = f" [{latency_color}]{ms}ms[/{latency_color}]"

    if msg.is_error:
        console.print(f"[{color}]{arrow} {method}[/{color}]{latency} [red]ERROR: {msg.error_message}[/red]")
    else:
        console.print(f"[{color}]{arrow} {method}[/{color}]{latency}")


async def run_proxy(
    config_path: Path | None = None,
    port: int = 0,
    server_name: str | None = None,
    use_tui: bool = True,
) -> None:
    """Run the MCP proxy."""
    config = load_config(config_path)

    if not config.servers:
        console.print("[red]No MCP servers found in config.[/red]")
        console.print("Provide a config with --config or place one in a known IDE location.")
        return

    # Select server
    if server_name:
        if server_name not in config.servers:
            console.print(f"[red]Server '{server_name}' not found in config.[/red]")
            console.print(f"Available: {', '.join(config.servers.keys())}")
            return
        server_config = config.servers[server_name]
    elif len(config.servers) == 1:
        server_config = next(iter(config.servers.values()))
    else:
        console.print("[yellow]Multiple servers found. Use --server to select one:[/yellow]")
        for name in config.servers:
            console.print(f"  - {name}")
        return

    if use_tui:
        try:
            from mcptools.tui.dashboard import run_tui_proxy
            await run_tui_proxy(server_config)
        except ImportError:
            console.print("[yellow]TUI not available, falling back to log mode.[/yellow]")
            use_tui = False

    if not use_tui:
        console.print(f"[bold]Proxying server:[/bold] {server_config.name}")
        console.print(f"[dim]Command: {server_config.command} {' '.join(server_config.args)}[/dim]")
        console.print("[dim]Ctrl+C to stop[/dim]\n")

        proxy = ProxyInterceptor(server_config, on_message=_print_message)
        try:
            await proxy.start()
        except KeyboardInterrupt:
            pass
        finally:
            await proxy.stop()
