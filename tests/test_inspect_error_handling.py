"""Tests for inspect error handling."""

from __future__ import annotations

import pytest

from mcptools.inspect.server import inspect_server


@pytest.mark.asyncio
async def test_inspect_nonexistent_command(capsys: pytest.CaptureFixture[str]) -> None:
    """Inspect should handle a nonexistent command gracefully."""
    await inspect_server(["nonexistent-command-xyz-12345"], timeout=3)
    captured = capsys.readouterr()
    assert "not found" in captured.out.lower() or "failed" in captured.out.lower()


@pytest.mark.asyncio
async def test_inspect_non_mcp_command(capsys: pytest.CaptureFixture[str]) -> None:
    """Inspect should handle a non-MCP command (echo) gracefully."""
    await inspect_server(["echo", "hello"], timeout=3)
    captured = capsys.readouterr()
    # Should either timeout or report invalid JSON / closed connection
    assert captured.out  # Should produce some error output
