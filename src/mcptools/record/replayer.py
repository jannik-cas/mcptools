"""Session replay — replays recorded MCP sessions."""

from __future__ import annotations

import asyncio
import fnmatch
import json
import time
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

console = Console()


async def run_replayer(
    session_path: Path,
    speed: float = 1.0,
    filter_method: str | None = None,
) -> None:
    """Replay a recorded MCP session."""
    with open(session_path) as f:
        session = json.load(f)

    messages = session.get("messages", [])
    version = session.get("mcptools_version", "?")
    duration = session.get("duration", 0)

    console.print(Panel(
        f"Session: {session_path.name}\n"
        f"Messages: {len(messages)} | Duration: {duration:.1f}s | Speed: {speed}x",
        title="MCP Session Replay",
        border_style="blue",
    ))

    # Filter messages if requested
    if filter_method:
        messages = [
            m for m in messages
            if fnmatch.fnmatch(m.get("data", {}).get("method", ""), filter_method)
            or (not m.get("data", {}).get("method") and _is_response_to_filtered(m, messages, filter_method))
        ]
        console.print(f"[dim]Filtered to {len(messages)} messages matching '{filter_method}'[/dim]")

    if not messages:
        console.print("[yellow]No messages to replay.[/yellow]")
        return

    console.print()

    prev_time = None
    for i, msg in enumerate(messages, 1):
        relative_time = msg.get("relative_time", 0)
        direction = msg.get("direction", "?")
        data = msg.get("data", {})

        # Simulate timing
        if prev_time is not None and speed > 0:
            delay = (relative_time - prev_time) / speed
            if delay > 0:
                await asyncio.sleep(min(delay, 2.0))  # Cap at 2s max delay
        prev_time = relative_time

        # Format output
        arrow = ">>>" if direction == "client_to_server" else "<<<"
        color = "cyan" if direction == "client_to_server" else "green"
        method = data.get("method", "(response)")

        is_error = "error" in data
        if is_error:
            color = "red"

        time_str = f"[dim]+{relative_time:.1f}s[/dim]"

        # Check for latency
        latency = ""
        if "_latency_ms" in data:
            ms = data["_latency_ms"]
            lat_color = "green" if ms < 500 else "yellow" if ms < 2000 else "red"
            latency = f" [{lat_color}]{ms}ms[/{lat_color}]"

        console.print(f"{time_str} [{color}]{arrow} {method}[/{color}]{latency}")

        # Show payload details for important messages
        if method and method.startswith("tools/call"):
            params = data.get("params", {})
            if params:
                console.print(f"  [dim]Tool: {params.get('name', '?')}[/dim]")

        if is_error:
            error = data.get("error", {})
            msg_text = error.get("message", str(error)) if isinstance(error, dict) else str(error)
            console.print(f"  [red]Error: {msg_text}[/red]")

    console.print(f"\n[dim]Replay complete — {len(messages)} messages[/dim]")


def _is_response_to_filtered(
    msg: dict[str, Any],
    all_messages: list[dict[str, Any]],
    pattern: str,
) -> bool:
    """Check if a response message corresponds to a filtered request."""
    msg_id = msg.get("data", {}).get("id")
    if msg_id is None:
        return False

    for m in all_messages:
        if (
            m.get("data", {}).get("id") == msg_id
            and m.get("data", {}).get("method")
            and fnmatch.fnmatch(m["data"]["method"], pattern)
        ):
            return True
    return False
