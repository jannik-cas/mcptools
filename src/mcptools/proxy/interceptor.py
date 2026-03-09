"""Core proxy logic — intercepts and forwards MCP traffic."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from pathlib import Path

from rich.console import Console

from mcptools.config.parser import ServerConfig, load_config, select_server
from mcptools.proxy.transport import McpMessage, StdinReader, StdioTransport, StdoutWriter

console = Console(stderr=True)

# Type alias for message callbacks
MessageCallback = Callable[[McpMessage], None]


class ProxyInterceptor:
    """Intercepts MCP traffic between client and server.

    Sits between an MCP client (reading from stdin) and an MCP server
    (spawned as a subprocess), capturing every JSON-RPC message that
    passes through.  An optional *on_message* callback is invoked for
    each captured message to drive the TUI or recording logic.

    Attributes:
        server_config: Configuration of the target MCP server.
        on_message: Optional callback invoked for every intercepted message.
        messages: Ordered list of all messages seen during the session.
    """

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
        """Stop the proxy and terminate the server subprocess."""
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
        err = msg.error_message
        console.print(f"[{color}]{arrow} {method}[/{color}]{latency} [red]ERROR: {err}[/red]")
    else:
        console.print(f"[{color}]{arrow} {method}[/{color}]{latency}")


async def run_proxy(
    config_path: Path | None = None,
    port: int = 0,
    server_name: str | None = None,
    use_tui: bool = True,
) -> None:
    """Run the MCP proxy.

    Loads the configuration, selects a server, and starts either the
    TUI dashboard or plain log-mode proxy.

    Args:
        config_path: Explicit config file path, or *None* to auto-detect.
        port: Reserved for future SSE proxy support.
        server_name: Name of the server to proxy (required when multiple
            servers are configured).
        use_tui: If *True*, launch the interactive Textual dashboard.
    """
    config = load_config(config_path)

    server_config = select_server(config, server_name)
    if server_config is None:
        if not config.servers:
            console.print("Provide a config with --config or place one in a known IDE location.")
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
