"""TUI dashboard for real-time MCP traffic visualization."""

from __future__ import annotations

import time
from typing import Any

from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import DataTable, Footer, Header, Label, Static

from mcptools.config.parser import ServerConfig
from mcptools.proxy.transport import McpMessage


class MessageLog(Static):
    """Widget displaying the scrolling message log."""

    def compose(self) -> ComposeResult:
        yield DataTable(id="messages-table")

    def on_mount(self) -> None:
        table = self.query_one("#messages-table", DataTable)
        table.add_columns("Time", "Dir", "Method", "Latency", "Status")
        table.cursor_type = "row"

    def add_message(self, msg: McpMessage) -> None:
        table = self.query_one("#messages-table", DataTable)

        timestamp = time.strftime("%H:%M:%S", time.localtime(msg.timestamp))
        direction = "→" if msg.direction == "client_to_server" else "←"
        method = msg.method or "(response)"

        latency = ""
        if "_latency_ms" in msg.data:
            ms = msg.data["_latency_ms"]
            latency = f"{ms}ms"

        if msg.is_error:
            status = Text("ERROR", style="bold red")
        elif msg.is_response:
            status = Text("OK", style="green")
        else:
            status = Text("REQ", style="cyan")

        dir_style = "cyan" if msg.direction == "client_to_server" else "green"

        table.add_row(
            timestamp,
            Text(direction, style=dir_style),
            method,
            latency,
            status,
        )
        table.scroll_end()


class StatsPanel(Static):
    """Widget showing live stats."""

    total_messages: reactive[int] = reactive(0)
    total_errors: reactive[int] = reactive(0)
    avg_latency: reactive[float] = reactive(0.0)
    server_name: reactive[str] = reactive("")

    def render(self) -> str:
        latency_str = f"{self.avg_latency:.0f}ms" if self.avg_latency > 0 else "-"
        return (
            f"Server: {self.server_name}\n"
            f"Messages: {self.total_messages}\n"
            f"Errors: {self.total_errors}\n"
            f"Avg Latency: {latency_str}"
        )


class McpDashboard(App):
    """Main TUI application for MCP traffic monitoring."""

    CSS = """
    Screen {
        layout: horizontal;
    }

    #sidebar {
        width: 30;
        dock: left;
        border: solid $accent;
        padding: 1;
    }

    #main {
        width: 1fr;
    }

    MessageLog {
        height: 1fr;
        border: solid $accent;
    }

    #detail-panel {
        height: 12;
        dock: bottom;
        border: solid $accent;
        padding: 1;
    }

    DataTable {
        height: 1fr;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("c", "clear", "Clear"),
    ]

    def __init__(self, server_config: ServerConfig) -> None:
        super().__init__()
        self.server_config = server_config
        self._latencies: list[float] = []

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal():
            with Vertical(id="sidebar"):
                yield StatsPanel(id="stats")
            with Vertical(id="main"):
                yield MessageLog(id="message-log")
                yield Static("Select a message to see details", id="detail-panel")
        yield Footer()

    def on_mount(self) -> None:
        stats = self.query_one("#stats", StatsPanel)
        stats.server_name = self.server_config.name

    def add_message(self, msg: McpMessage) -> None:
        """Add a message from the proxy to the dashboard."""
        log = self.query_one("#message-log", MessageLog)
        log.add_message(msg)

        stats = self.query_one("#stats", StatsPanel)
        stats.total_messages += 1

        if msg.is_error:
            stats.total_errors += 1

        if "_latency_ms" in msg.data:
            self._latencies.append(msg.data["_latency_ms"])
            stats.avg_latency = sum(self._latencies) / len(self._latencies)

    def action_clear(self) -> None:
        """Clear the message log."""
        table = self.query_one("#messages-table", DataTable)
        table.clear()
        self._latencies.clear()
        stats = self.query_one("#stats", StatsPanel)
        stats.total_messages = 0
        stats.total_errors = 0
        stats.avg_latency = 0.0


async def run_tui_proxy(server_config: ServerConfig) -> None:
    """Run the proxy with the TUI dashboard."""
    from mcptools.proxy.interceptor import ProxyInterceptor

    app = McpDashboard(server_config)

    def on_message(msg: McpMessage) -> None:
        app.call_from_thread(app.add_message, msg)

    proxy = ProxyInterceptor(server_config, on_message=on_message)

    async def run_proxy_background() -> None:
        try:
            await proxy.start()
        except Exception:
            pass

    # Run proxy in background, TUI in foreground
    import asyncio

    proxy_task = asyncio.create_task(run_proxy_background())

    try:
        await app.run_async()
    finally:
        proxy_task.cancel()
        await proxy.stop()
