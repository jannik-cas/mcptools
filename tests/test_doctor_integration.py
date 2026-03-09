"""Integration-style tests for doctor checks."""

from __future__ import annotations

import pytest

from mcptools.config.parser import ServerConfig
from mcptools.doctor.checks import check_server


@pytest.mark.asyncio
async def test_doctor_nonexistent_command() -> None:
    """Doctor should report error for a command that doesn't exist."""
    server = ServerConfig(
        name="broken",
        command="nonexistent-command-xyz-12345",
        args=[],
    )
    result = await check_server("broken", server, timeout=5)
    assert result.status == "error"
    assert "not found" in result.message.lower() or "failed" in result.message.lower()


@pytest.mark.asyncio
async def test_doctor_non_mcp_command() -> None:
    """Doctor should report error for a command that exists but isn't MCP (e.g., echo)."""
    server = ServerConfig(
        name="echo",
        command="echo",
        args=["hello"],
    )
    result = await check_server("echo", server, timeout=3)
    assert result.status == "error"


@pytest.mark.asyncio
async def test_doctor_empty_command() -> None:
    """Doctor should report error when no command is specified."""
    server = ServerConfig(
        name="empty",
        command="",
        args=[],
    )
    result = await check_server("empty", server, timeout=5)
    assert result.status == "error"


@pytest.mark.asyncio
async def test_doctor_missing_env_vars() -> None:
    """Doctor should warn about unresolved env vars."""
    server = ServerConfig(
        name="envtest",
        command="echo",
        args=[],
        env={"API_KEY": "${API_KEY}"},
    )
    result = await check_server("envtest", server, timeout=5)
    assert result.status == "warning"
    assert "env" in result.message.lower()
