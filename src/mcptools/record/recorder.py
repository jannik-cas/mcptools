"""Session recording — captures MCP traffic to a JSON file."""

from __future__ import annotations

import json
import time
from pathlib import Path

from rich.console import Console

from mcptools.config.parser import load_config, ServerConfig
from mcptools.proxy.interceptor import ProxyInterceptor, _print_message
from mcptools.proxy.transport import McpMessage

console = Console(stderr=True)


class SessionRecorder:
    """Records MCP messages to a JSON file."""

    def __init__(self, output_path: Path) -> None:
        self.output_path = output_path
        self.messages: list[dict] = []
        self.start_time = time.time()

    def on_message(self, msg: McpMessage) -> None:
        """Callback for each intercepted message."""
        self.messages.append({
            "timestamp": msg.timestamp,
            "relative_time": msg.timestamp - self.start_time,
            "direction": msg.direction,
            "data": msg.data,
        })
        _print_message(msg)

    def save(self) -> None:
        """Save recorded session to disk."""
        session = {
            "mcptools_version": "0.1.0",
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
    """Run the proxy in recording mode."""
    config = load_config(config_path)

    if not config.servers:
        console.print("[red]No MCP servers found in config.[/red]")
        return

    # Select server
    if server_name:
        if server_name not in config.servers:
            console.print(f"[red]Server '{server_name}' not found.[/red]")
            return
        server_config = config.servers[server_name]
    elif len(config.servers) == 1:
        server_config = next(iter(config.servers.values()))
    else:
        console.print("[yellow]Multiple servers. Use --server to pick one:[/yellow]")
        for name in config.servers:
            console.print(f"  - {name}")
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
