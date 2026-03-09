"""TUI dashboard for real-time MCP traffic visualization.

Provides a Textual-based terminal UI that displays live message flow,
statistics, and JSON payloads as the proxy intercepts MCP traffic.
"""

from __future__ import annotations

import json
import time

from rich.syntax import Syntax
from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import DataTable, Footer, Header, Static

from mcptools.config.parser import ServerConfig
from mcptools.proxy.transport import McpMessage


class MessageLog(Static):
    """Widget displaying the scrolling message log.

    Renders a ``DataTable`` with columns for time, direction, method,
    latency, and status of each intercepted message.
    """

    def compose(self) -> ComposeResult:
        yield DataTable(id="messages-table")

    def on_mount(self) -> None:
        table = self.query_one("#messages-table", DataTable)
        table.add_columns("Time", "Dir", "Method", "Latency", "Status")
        table.cursor_type = "row"

    def add_message(self, msg: McpMessage) -> None:
        """Append a message row to the log table.

        Args:
            msg: The intercepted MCP message to display.
        """
        table = self.query_one("#messages-table", DataTable)

        timestamp = time.strftime("%H:%M:%S", time.localtime(msg.timestamp))
        direction = "\u2192" if msg.direction == "client_to_server" else "\u2190"
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
    """Widget showing live session statistics.

    Displays the server name, total message count, error count, and
    rolling average latency.
    """

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
    """Main TUI application for MCP traffic monitoring.

    Layout consists of a sidebar showing live stats and a main area
    with a scrolling message log and a detail panel that displays the
    full JSON payload of the selected message.

    Args:
        server_config: Configuration of the MCP server being proxied.
    """

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
        self._messages: list[McpMessage] = []

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
        """Add a message from the proxy to the dashboard.

        Args:
            msg: The intercepted MCP message.
        """
        self._messages.append(msg)
        log = self.query_one("#message-log", MessageLog)
        log.add_message(msg)

        stats = self.query_one("#stats", StatsPanel)
        stats.total_messages += 1

        if msg.is_error:
            stats.total_errors += 1

        if "_latency_ms" in msg.data:
            self._latencies.append(msg.data["_latency_ms"])
            stats.avg_latency = sum(self._latencies) / len(self._latencies)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Show full JSON payload when a row is selected."""
        row_index = event.cursor_row
        if 0 <= row_index < len(self._messages):
            msg = self._messages[row_index]
            payload = json.dumps(msg.data, indent=2)
            detail = self.query_one("#detail-panel", Static)
            detail.update(Syntax(payload, "json", theme="monokai", line_numbers=False))

    def action_clear(self) -> None:
        """Clear the message log and reset statistics."""
        table = self.query_one("#messages-table", DataTable)
        table.clear()
        self._messages.clear()
        self._latencies.clear()
        stats = self.query_one("#stats", StatsPanel)
        stats.total_messages = 0
        stats.total_errors = 0
        stats.avg_latency = 0.0
        detail = self.query_one("#detail-panel", Static)
        detail.update("Select a message to see details")


async def run_tui_proxy(server_config: ServerConfig) -> None:
    """Run the proxy with the TUI dashboard.

    Starts the proxy as a background async task and runs the Textual
    application in the foreground.

    Args:
        server_config: Configuration of the MCP server to proxy.
    """
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
