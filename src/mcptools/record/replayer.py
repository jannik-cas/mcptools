"""Session replay — replays recorded MCP sessions.

Reads a previously recorded session JSON file and re-displays the
messages with their original timing (optionally sped up or filtered).
"""

from __future__ import annotations

import asyncio
import fnmatch
import json
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel

console = Console()


def _filter_messages(
    messages: list[dict[str, Any]],
    pattern: str,
) -> list[dict[str, Any]]:
    """Filter recorded messages by method name glob pattern.

    Keeps requests whose method matches *pattern* **and** their
    corresponding responses.  Response matching works by collecting
    the ``id`` fields of all matching requests into a set, then
    including any response whose ``id`` is in that set.  This ensures
    that filtering by e.g. ``"tools/*"`` shows both the request and
    its server response.

    Args:
        messages: Raw message dicts from a recorded session file.
        pattern: ``fnmatch``-style glob pattern to match against
            JSON-RPC method names (e.g. ``"tools/*"``).

    Returns:
        Filtered list preserving original order, containing matching
        requests and their paired responses.
    """
    # Pre-build set of request IDs matching the filter for O(1) lookup
    filtered_ids: set[int | str] = set()
    for m in messages:
        method = m.get("data", {}).get("method")
        msg_id = m.get("data", {}).get("id")
        if method and fnmatch.fnmatch(method, pattern) and msg_id is not None:
            filtered_ids.add(msg_id)

    return [
        m
        for m in messages
        if fnmatch.fnmatch(m.get("data", {}).get("method", ""), pattern)
        or (not m.get("data", {}).get("method") and m.get("data", {}).get("id") in filtered_ids)
    ]


def _render_message(data: dict[str, Any], direction: str, relative_time: float) -> None:
    """Render a single replayed message to the console with Rich formatting.

    Displays the message as a single line with direction arrows
    (``>>>`` for client-to-server, ``<<<`` for server-to-client),
    colour-coded by type (cyan/green for normal, red for errors),
    and optional latency annotation.  ``tools/call`` requests also
    show the invoked tool name on a detail line.

    Args:
        data: Raw JSON-RPC message data dict.
        direction: ``"client_to_server"`` or ``"server_to_client"``.
        relative_time: Seconds elapsed since the start of the original
            recording session, shown as a ``+N.Ns`` prefix.
    """
    arrow = ">>>" if direction == "client_to_server" else "<<<"
    color = "cyan" if direction == "client_to_server" else "green"
    method = data.get("method", "(response)")

    is_error = "error" in data
    if is_error:
        color = "red"

    time_str = f"[dim]+{relative_time:.1f}s[/dim]"

    latency = ""
    if "_latency_ms" in data:
        ms = data["_latency_ms"]
        lat_color = "green" if ms < 500 else "yellow" if ms < 2000 else "red"
        latency = f" [{lat_color}]{ms}ms[/{lat_color}]"

    console.print(f"{time_str} [{color}]{arrow} {method}[/{color}]{latency}")

    if method and method.startswith("tools/call"):
        params = data.get("params", {})
        if params:
            console.print(f"  [dim]Tool: {params.get('name', '?')}[/dim]")

    if is_error:
        error = data.get("error", {})
        msg_text = error.get("message", str(error)) if isinstance(error, dict) else str(error)
        console.print(f"  [red]Error: {msg_text}[/red]")


async def run_replayer(
    session_path: Path,
    speed: float = 1.0,
    filter_method: str | None = None,
) -> None:
    """Replay a recorded MCP session.

    Reads the session file, optionally filters by method name, and
    prints each message to the console with simulated timing.

    Args:
        session_path: Path to the recorded session JSON file.
        speed: Playback speed multiplier (e.g. ``2.0`` for double speed).
        filter_method: Optional glob pattern to filter messages by
            method name (e.g. ``"tools/*"``).  Matching responses are
            included automatically.
    """
    with open(session_path) as f:
        session = json.load(f)

    messages = session.get("messages", [])
    duration = session.get("duration", 0)

    console.print(
        Panel(
            f"Session: {session_path.name}\n"
            f"Messages: {len(messages)} | Duration: {duration:.1f}s | Speed: {speed}x",
            title="MCP Session Replay",
            border_style="blue",
        )
    )

    if filter_method:
        messages = _filter_messages(messages, filter_method)
        console.print(f"[dim]Filtered to {len(messages)} messages matching '{filter_method}'[/dim]")

    if not messages:
        console.print("[yellow]No messages to replay.[/yellow]")
        return

    console.print()

    prev_time = None
    for msg in messages:
        relative_time = msg.get("relative_time", 0)

        # Simulate timing
        if prev_time is not None and speed > 0:
            delay = (relative_time - prev_time) / speed
            if delay > 0:
                await asyncio.sleep(min(delay, 2.0))  # Cap at 2s max delay
        prev_time = relative_time

        _render_message(msg.get("data", {}), msg.get("direction", "?"), relative_time)

    console.print(f"\n[dim]Replay complete — {len(messages)} messages[/dim]")
