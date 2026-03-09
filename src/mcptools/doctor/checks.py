"""Health checks and diagnostics for MCP servers."""

from __future__ import annotations

import asyncio
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from mcptools.config.parser import load_config, find_config, McpConfig, ServerConfig, CONFIG_LOCATIONS
from mcptools.proxy.transport import StdioTransport

console = Console()


@dataclass
class CheckResult:
    """Result of a single server health check."""

    server_name: str
    status: str  # "healthy", "error", "warning", "skipped"
    message: str
    tool_count: int = 0
    resource_count: int = 0
    prompt_count: int = 0
    latency_ms: float = 0
    details: list[str] | None = None


async def check_server(name: str, server: ServerConfig, timeout: int = 10) -> CheckResult:
    """Check health of a single MCP server."""

    # Check command exists
    if server.transport == "stdio" and not server.command:
        return CheckResult(
            server_name=name,
            status="error",
            message="No command specified",
        )

    # Check for missing env vars
    missing_env = []
    for key, value in server.env.items():
        if value.startswith("${") and value.endswith("}"):
            missing_env.append(key)

    if missing_env:
        return CheckResult(
            server_name=name,
            status="warning",
            message=f"Missing env vars: {', '.join(missing_env)}",
            details=[f"Set {k} in your environment" for k in missing_env],
        )

    # Try connecting
    command = [server.command, *server.args]
    transport = StdioTransport(command=command, env=server.env)

    try:
        await transport.start()
    except FileNotFoundError:
        return CheckResult(
            server_name=name,
            status="error",
            message=f"Command not found: {server.command}",
            details=[f"Ensure '{server.command}' is installed and in your PATH"],
        )
    except Exception as e:
        return CheckResult(
            server_name=name,
            status="error",
            message=f"Failed to start: {e}",
        )

    start_time = time.time()

    try:
        # Initialize
        init_msg = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "mcptools-doctor", "version": "0.1.0"},
            },
        }
        await transport.send(init_msg)
        response = await asyncio.wait_for(transport.receive(), timeout=timeout)

        if response is None:
            return CheckResult(
                server_name=name,
                status="error",
                message="Server closed connection during init",
            )

        if "error" in response:
            error = response["error"]
            msg = error.get("message", str(error)) if isinstance(error, dict) else str(error)
            return CheckResult(
                server_name=name,
                status="error",
                message=f"Init error: {msg}",
            )

        capabilities = response.get("result", {}).get("capabilities", {})

        # Send initialized notification
        await transport.send({"jsonrpc": "2.0", "method": "notifications/initialized"})

        tool_count = 0
        resource_count = 0
        prompt_count = 0

        # Count tools
        if "tools" in capabilities:
            await transport.send({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
            tools_resp = await asyncio.wait_for(transport.receive(), timeout=timeout)
            if tools_resp and "result" in tools_resp:
                tool_count = len(tools_resp["result"].get("tools", []))

        # Count resources
        if "resources" in capabilities:
            await transport.send({"jsonrpc": "2.0", "id": 3, "method": "resources/list"})
            res_resp = await asyncio.wait_for(transport.receive(), timeout=timeout)
            if res_resp and "result" in res_resp:
                resource_count = len(res_resp["result"].get("resources", []))

        # Count prompts
        if "prompts" in capabilities:
            await transport.send({"jsonrpc": "2.0", "id": 4, "method": "prompts/list"})
            prompts_resp = await asyncio.wait_for(transport.receive(), timeout=timeout)
            if prompts_resp and "result" in prompts_resp:
                prompt_count = len(prompts_resp["result"].get("prompts", []))

        latency = (time.time() - start_time) * 1000

        # Determine status based on latency
        status = "healthy"
        warnings = []
        if latency > 5000:
            status = "warning"
            warnings.append(f"Slow response ({latency:.0f}ms)")
        elif latency > 2000:
            warnings.append(f"Moderate latency ({latency:.0f}ms)")

        parts = []
        if tool_count:
            parts.append(f"{tool_count} tool{'s' if tool_count != 1 else ''}")
        if resource_count:
            parts.append(f"{resource_count} resource{'s' if resource_count != 1 else ''}")
        if prompt_count:
            parts.append(f"{prompt_count} prompt{'s' if prompt_count != 1 else ''}")

        message = ", ".join(parts) if parts else "connected (no capabilities)"
        if warnings:
            message += f" — {'; '.join(warnings)}"

        return CheckResult(
            server_name=name,
            status=status,
            message=message,
            tool_count=tool_count,
            resource_count=resource_count,
            prompt_count=prompt_count,
            latency_ms=latency,
        )

    except asyncio.TimeoutError:
        return CheckResult(
            server_name=name,
            status="error",
            message=f"Connection timeout ({timeout}s)",
            details=["Try increasing --timeout", "Check if the server starts correctly"],
        )
    except json.JSONDecodeError:
        return CheckResult(
            server_name=name,
            status="error",
            message="Invalid JSON response from server",
            details=["Server may be writing non-JSON to stdout"],
        )
    except Exception as e:
        return CheckResult(
            server_name=name,
            status="error",
            message=f"Unexpected error: {e}",
        )
    finally:
        await transport.stop()


def _status_icon(status: str) -> str:
    if status == "healthy":
        return "[green]✓[/green]"
    elif status == "error":
        return "[red]✗[/red]"
    elif status == "warning":
        return "[yellow]⚠[/yellow]"
    return "[dim]○[/dim]"


async def run_doctor(
    config_path: Path | None = None,
    server_names: list[str] | None = None,
    timeout: int = 10,
) -> None:
    """Run health checks on MCP servers."""
    # Find config
    if config_path is None:
        config_path = find_config()

    if config_path is None:
        console.print("[yellow]No MCP config file found.[/yellow]")
        console.print("\nSearched locations:")
        for name, path in CONFIG_LOCATIONS:
            exists = "[green]exists[/green]" if path.exists() else "[dim]not found[/dim]"
            console.print(f"  {name}: {path} ({exists})")
        console.print("\nUse --config to specify a config file path.")
        return

    console.print(f"[dim]Config:[/dim] {config_path}\n")

    config = load_config(config_path)

    if not config.servers:
        console.print("[yellow]No servers found in config file.[/yellow]")
        return

    # Filter servers
    servers_to_check = config.servers
    if server_names:
        servers_to_check = {
            k: v for k, v in config.servers.items() if k in server_names
        }
        missing = set(server_names) - set(servers_to_check.keys())
        for name in missing:
            console.print(f"[yellow]Server '{name}' not found in config.[/yellow]")

    # Run checks concurrently
    tasks = {
        name: asyncio.create_task(check_server(name, server, timeout))
        for name, server in servers_to_check.items()
    }

    results: list[CheckResult] = []
    for name, task in tasks.items():
        console.print(f"  Checking [bold]{name}[/bold]...", end=" ")
        result = await task
        results.append(result)
        console.print(f"{_status_icon(result.status)} {result.message}")

        if result.details:
            for detail in result.details:
                console.print(f"    [dim]→ {detail}[/dim]")

    # Summary
    console.print()
    healthy = sum(1 for r in results if r.status == "healthy")
    errors = sum(1 for r in results if r.status == "error")
    warnings = sum(1 for r in results if r.status == "warning")

    summary_parts = []
    if healthy:
        summary_parts.append(f"[green]{healthy} healthy[/green]")
    if warnings:
        summary_parts.append(f"[yellow]{warnings} warning{'s' if warnings != 1 else ''}[/yellow]")
    if errors:
        summary_parts.append(f"[red]{errors} error{'s' if errors != 1 else ''}[/red]")

    console.print(f"Summary: {', '.join(summary_parts)}")
