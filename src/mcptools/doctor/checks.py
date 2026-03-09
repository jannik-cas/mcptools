"""Health checks and diagnostics for MCP servers."""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Literal

from pydantic import BaseModel
from rich.console import Console

from mcptools.config.parser import (
    CONFIG_LOCATIONS,
    ServerConfig,
    find_config,
    load_config,
)
from mcptools.handshake import McpInitError, mcp_initialize
from mcptools.jsonrpc import IdGenerator, make_request
from mcptools.proxy.transport import StdioTransport

console = Console()

Status = Literal["healthy", "error", "warning", "skipped"]


class CheckResult(BaseModel):
    """Result of a single server health check.

    Attributes:
        server_name: Name of the server that was checked.
        status: One of ``"healthy"``, ``"error"``, ``"warning"``, or ``"skipped"``.
        message: Human-readable summary of the check outcome.
        tool_count: Number of tools the server exposes.
        resource_count: Number of resources the server exposes.
        prompt_count: Number of prompts the server exposes.
        latency_ms: Round-trip time of the health check in milliseconds.
        details: Optional list of actionable hints for the user.
    """

    server_name: str
    status: Status
    message: str
    tool_count: int = 0
    resource_count: int = 0
    prompt_count: int = 0
    latency_ms: float = 0
    details: list[str] | None = None


def _validate_server_config(name: str, server: ServerConfig) -> CheckResult | None:
    """Check for configuration problems that would make connecting pointless.

    Catches two classes of issue before we spend time spawning a
    subprocess:

    * **Missing command** — the ``command`` field is empty (stdio
      transport requires an executable).
    * **Unresolved environment variables** — env values still in
      ``${VAR}`` form indicate the variable was not present in the
      host environment at parse time.

    Args:
        name: Display name for this server.
        server: Parsed server configuration.

    Returns:
        A ``CheckResult`` with ``"error"`` or ``"warning"`` status if
        validation fails, or *None* if the config looks OK to proceed.
    """
    if server.transport == "stdio" and not server.command:
        return CheckResult(
            server_name=name,
            status="error",
            message="No command specified",
        )

    missing_env = [
        key for key, value in server.env.items() if value.startswith("${") and value.endswith("}")
    ]
    if missing_env:
        return CheckResult(
            server_name=name,
            status="warning",
            message=f"Missing env vars: {', '.join(missing_env)}",
            details=[f"Set {k} in your environment" for k in missing_env],
        )

    return None


async def _count_capabilities(
    transport: StdioTransport,
    capabilities: dict,
    ids: IdGenerator,
    timeout: int,
) -> tuple[int, int, int]:
    """Enumerate tools, resources, and prompts from a connected server.

    Sends ``tools/list``, ``resources/list``, and ``prompts/list``
    requests for each capability the server advertised during the
    handshake.  Capabilities not present in the *capabilities* dict
    are skipped (counted as zero).

    Args:
        transport: Active server transport (must already be initialised).
        capabilities: Capabilities dict from the initialize response,
            used to decide which list requests to send.
        ids: ID generator for assigning request IDs.
        timeout: Seconds to wait for each individual list response.

    Returns:
        Tuple of ``(tool_count, resource_count, prompt_count)``.
    """
    counts = []
    for capability, method, key in [
        ("tools", "tools/list", "tools"),
        ("resources", "resources/list", "resources"),
        ("prompts", "prompts/list", "prompts"),
    ]:
        if capability not in capabilities:
            counts.append(0)
            continue
        await transport.send(make_request(method, msg_id=ids.next()))
        resp = await asyncio.wait_for(transport.receive(), timeout=timeout)
        if resp and "result" in resp:
            counts.append(len(resp["result"].get(key, [])))
        else:
            counts.append(0)

    return counts[0], counts[1], counts[2]


def _build_health_result(
    name: str,
    tool_count: int,
    resource_count: int,
    prompt_count: int,
    latency: float,
) -> CheckResult:
    """Build a ``CheckResult`` by assessing capability counts and latency.

    Applies the following latency thresholds:

    * **> 5 000 ms** — ``"warning"`` status with "Slow response" note.
    * **> 2 000 ms** — ``"healthy"`` status with "Moderate latency" note.
    * **Otherwise** — ``"healthy"`` with no latency remark.

    The summary message lists the counts (e.g. ``"3 tools, 1 resource"``)
    followed by any latency warnings.

    Args:
        name: Server display name.
        tool_count: Number of tools the server exposes.
        resource_count: Number of resources the server exposes.
        prompt_count: Number of prompts the server exposes.
        latency: Total round-trip time of the health check in milliseconds.

    Returns:
        A ``CheckResult`` with the computed status and human-readable
        summary message.
    """
    status: Status = "healthy"
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


async def check_server(name: str, server: ServerConfig, timeout: int = 10) -> CheckResult:
    """Check health of a single MCP server.

    Validates configuration, connects to the server, and enumerates
    its capabilities.

    Args:
        name: Display name for this server entry.
        server: Parsed server configuration.
        timeout: Seconds to wait for the server to respond.

    Returns:
        A ``CheckResult`` summarising the server's health.
    """
    config_error = _validate_server_config(name, server)
    if config_error is not None:
        return config_error

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

    ids = IdGenerator()
    start_time = time.time()

    try:
        init_result = await mcp_initialize(
            transport, timeout, ids=ids, client_name="mcptools-doctor"
        )
        capabilities = init_result.get("capabilities", {})
        tool_count, resource_count, prompt_count = await _count_capabilities(
            transport, capabilities, ids, timeout
        )
        latency = (time.time() - start_time) * 1000

        return _build_health_result(name, tool_count, resource_count, prompt_count, latency)

    except McpInitError as e:
        return CheckResult(server_name=name, status="error", message=str(e))
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
        return CheckResult(server_name=name, status="error", message=f"Unexpected error: {e}")
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


def _format_results_json(config_path: Path, results: list[CheckResult]) -> str:
    """Serialise check results to the ``--json`` output format.

    Produces a JSON object with a ``config`` path and a ``servers``
    array.  Each server entry uses short keys (``name``, ``tools``,
    ``resources``, ``prompts``) for a compact, script-friendly
    representation.

    Args:
        config_path: Config file path included as metadata in the output.
        results: List of ``CheckResult`` instances to serialise.

    Returns:
        Pretty-printed JSON string (2-space indent).
    """
    output = {
        "config": str(config_path),
        "servers": [
            {
                "name": r.server_name,
                "status": r.status,
                "message": r.message,
                "tools": r.tool_count,
                "resources": r.resource_count,
                "prompts": r.prompt_count,
                "latency_ms": round(r.latency_ms, 1),
            }
            for r in results
        ],
    }
    return json.dumps(output, indent=2)


def _print_summary(results: list[CheckResult]) -> None:
    """Print a coloured one-line summary of all check outcomes.

    Groups results by status and prints counts with colour coding
    (green for healthy, yellow for warnings, red for errors).

    Args:
        results: List of ``CheckResult`` instances from the completed
            health checks.
    """
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


async def run_doctor(
    config_path: Path | None = None,
    server_names: list[str] | None = None,
    timeout: int = 10,
    json_output: bool = False,
) -> None:
    """Run health checks on all configured MCP servers.

    Loads the configuration, then checks each server concurrently.
    Outputs results as a Rich-formatted table or as JSON.

    Args:
        config_path: Explicit path to a config file, or *None* to auto-detect.
        server_names: Optional list of server names to check (default: all).
        timeout: Seconds to wait per server.
        json_output: If *True*, emit results as a JSON object.
    """
    # Find config
    if config_path is None:
        config_path = find_config()

    if config_path is None:
        if json_output:
            print(json.dumps({"error": "No MCP config file found"}))
        else:
            console.print("[yellow]No MCP config file found.[/yellow]")
            console.print("\nSearched locations:")
            for name, path in CONFIG_LOCATIONS:
                exists = "[green]exists[/green]" if path.exists() else "[dim]not found[/dim]"
                console.print(f"  {name}: {path} ({exists})")
            console.print("\nUse --config to specify a config file path.")
        return

    if not json_output:
        console.print(f"[dim]Config:[/dim] {config_path}\n")

    config = load_config(config_path)

    if not config.servers:
        if json_output:
            print(json.dumps({"error": "No servers found in config file"}))
        else:
            console.print("[yellow]No servers found in config file.[/yellow]")
        return

    # Filter servers
    servers_to_check = config.servers
    if server_names:
        servers_to_check = {k: v for k, v in config.servers.items() if k in server_names}
        missing = set(server_names) - set(servers_to_check.keys())
        if not json_output:
            for name in missing:
                console.print(f"[yellow]Server '{name}' not found in config.[/yellow]")

    # Run checks concurrently
    tasks = {
        name: asyncio.create_task(check_server(name, server, timeout))
        for name, server in servers_to_check.items()
    }

    results: list[CheckResult] = []
    for name, task in tasks.items():
        if not json_output:
            console.print(f"  Checking [bold]{name}[/bold]...", end=" ")
        result = await task
        results.append(result)
        if not json_output:
            console.print(f"{_status_icon(result.status)} {result.message}")
            if result.details:
                for detail in result.details:
                    console.print(f"    [dim]→ {detail}[/dim]")

    if json_output:
        print(_format_results_json(config_path, results))
    else:
        _print_summary(results)
