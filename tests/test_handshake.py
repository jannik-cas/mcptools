"""Tests for shared handshake helpers."""

from __future__ import annotations

import json
from unittest.mock import patch

from mcptools.handshake import McpInitError, emit_error


def test_emit_error_plain() -> None:
    """emit_error prints red Rich markup to the console."""
    with patch("mcptools.handshake.console") as mock_console:
        emit_error("something broke")
        mock_console.print.assert_called_once_with("[red]something broke[/red]")


def test_emit_error_json(capsys) -> None:
    """emit_error prints a JSON object when json_output=True."""
    emit_error("something broke", json_output=True)
    captured = capsys.readouterr()
    parsed = json.loads(captured.out)
    assert parsed == {"error": "something broke"}


def test_mcp_init_error_is_exception() -> None:
    """McpInitError is a standard Exception subclass."""
    err = McpInitError("handshake failed")
    assert isinstance(err, Exception)
    assert str(err) == "handshake failed"


def test_emit_error_json_special_chars(capsys) -> None:
    """emit_error handles special characters in JSON mode."""
    emit_error('quote "test" & <angle>', json_output=True)
    captured = capsys.readouterr()
    parsed = json.loads(captured.out)
    assert parsed["error"] == 'quote "test" & <angle>'
