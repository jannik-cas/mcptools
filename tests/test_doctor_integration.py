"""Integration-style tests for doctor checks."""

from __future__ import annotations

import json

import pytest

from mcptools.config.parser import ServerConfig
from mcptools.doctor.checks import (
    CheckResult,
    _build_health_result,
    _format_results_json,
    _validate_server_config,
    check_server,
)


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


# --- Unit tests for extracted helpers ---


def test_check_result_is_pydantic() -> None:
    """CheckResult should be a Pydantic BaseModel with validation."""
    result = CheckResult(server_name="test", status="healthy", message="ok")
    assert result.server_name == "test"
    assert result.tool_count == 0  # default

    with pytest.raises(Exception):
        CheckResult(server_name="test", status="invalid_status", message="bad")


def test_check_result_model_dump() -> None:
    """CheckResult should support model_dump for serialisation."""
    result = CheckResult(server_name="s", status="error", message="fail", tool_count=3)
    d = result.model_dump()
    assert d["server_name"] == "s"
    assert d["tool_count"] == 3


def test_validate_server_config_ok() -> None:
    """Valid config should return None."""
    server = ServerConfig(name="ok", command="npx", args=["server"])
    assert _validate_server_config("ok", server) is None


def test_validate_server_config_no_command() -> None:
    """Empty command should return an error CheckResult."""
    server = ServerConfig(name="empty", command="")
    result = _validate_server_config("empty", server)
    assert result is not None
    assert result.status == "error"


def test_validate_server_config_missing_env() -> None:
    """Unresolved env vars should return a warning CheckResult."""
    server = ServerConfig(name="e", command="x", env={"KEY": "${KEY}"})
    result = _validate_server_config("e", server)
    assert result is not None
    assert result.status == "warning"


def test_build_health_result_healthy() -> None:
    """Low latency should produce healthy status."""
    result = _build_health_result("s", 5, 2, 1, 100.0)
    assert result.status == "healthy"
    assert "5 tools" in result.message


def test_build_health_result_slow() -> None:
    """Very high latency should produce warning status."""
    result = _build_health_result("s", 1, 0, 0, 6000.0)
    assert result.status == "warning"
    assert "Slow" in result.message


def test_format_results_json() -> None:
    """JSON output should contain the expected keys."""
    from pathlib import Path

    results = [CheckResult(server_name="a", status="healthy", message="ok", tool_count=2)]
    output = json.loads(_format_results_json(Path("/tmp/test.json"), results))
    assert output["servers"][0]["name"] == "a"
    assert output["servers"][0]["tools"] == 2
