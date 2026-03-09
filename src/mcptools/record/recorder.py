"""Session recording — captures MCP traffic to a JSON file."""

from __future__ import annotations

import json
import time
from pathlib import Path

from rich.console import Console

import mcptools
from mcptools.config.parser import load_config, select_server
from mcptools.proxy.interceptor import ProxyInterceptor, _print_message
from mcptools.proxy.transport import McpMessage

console = Console(stderr=True)


class SessionRecorder:
    """Records MCP messages to a JSON file.

    Designed to be used as an *on_message* callback for
    :class:`~mcptools.proxy.interceptor.ProxyInterceptor`.  Messages
    are accumulated in memory and flushed to disk via :meth:`save`.

    Attributes:
        output_path: Destination file for the recorded session.
        messages: Accumulated message dicts.
        start_time: Epoch timestamp when recording began.
    """

    def __init__(self, output_path: Path) -> None:
        self.output_path = output_path
        self.messages: list[dict] = []
        self.start_time = time.time()

    def on_message(self, msg: McpMessage) -> None:
        """Callback for each intercepted message.

        Args:
            msg: The captured MCP message.
        """
        self.messages.append(
            {
                "timestamp": msg.timestamp,
                "relative_time": msg.timestamp - self.start_time,
                "direction": msg.direction,
                "data": msg.data,
            }
        )
        _print_message(msg)

    def save(self) -> None:
        """Save the recorded session to disk as JSON.

        Creates parent directories if needed.  The file includes
        metadata (version, duration, message count) alongside the
        message array.
        """
        session = {
            "mcptools_version": mcptools.__version__,
            "recorded_at": self.start_time,
            "duration": time.time() - self.start_time,
            "message_count": len(self.messages),
            "messages": self.messages,
        }

        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.output_path, "w") as f:
            json.dump(session, f, indent=2)

        console.print(f"\n[green]Session saved:[/green] {self.output_path}")
        console.print(f"[dim]{len(self.messages)} messages recorded[/dim]")


async def run_recorder(
    config_path: Path | None = None,
    output_path: Path = Path("session.json"),
    server_name: str | None = None,
) -> None:
    """Run the proxy in recording mode.

    All intercepted messages are captured and written to *output_path*
    when the session ends (Ctrl+C).

    Args:
        config_path: Explicit config file path, or *None* to auto-detect.
        output_path: Destination file for the recorded session.
        server_name: Name of the server to record (required when multiple
            servers are configured).
    """
    config = load_config(config_path)

    server_config = select_server(config, server_name)
    if server_config is None:
        return

    recorder = SessionRecorder(output_path)

    console.print(f"[bold]Recording:[/bold] {server_config.name}")
    console.print(f"[bold]Output:[/bold] {output_path}")
    console.print("[dim]Ctrl+C to stop and save[/dim]\n")

    proxy = ProxyInterceptor(server_config, on_message=recorder.on_message)

    try:
        await proxy.start()
    except KeyboardInterrupt:
        pass
    finally:
        recorder.save()
        await proxy.stop()
