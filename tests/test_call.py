"""Tests for the call command."""

from __future__ import annotations

import json

from click.testing import CliRunner

from mcptools.cli import cli


def test_call_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["call", "--help"])
    assert result.exit_code == 0
    assert "--tool" in result.output
    assert "--args" in result.output
    assert "--json" in result.output


def test_call_invalid_json_args():
    runner = CliRunner()
    result = runner.invoke(cli, ["call", "echo", "hello", "--tool", "test", "--args", "not json"])
    assert result.exit_code == 1
    assert "Invalid JSON" in result.output


def test_call_nonexistent_command():
    """Calling a tool on a nonexistent server should fail gracefully."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["call", "nonexistent-xyz-cmd", "--tool", "test"],
    )
    assert result.exit_code == 0
    assert "Command not found" in result.output


def test_call_nonexistent_command_json():
    """JSON mode should output a proper error object."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["call", "nonexistent-xyz-cmd", "--tool", "test", "--json"],
    )
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "error" in data
    assert "Command not found" in data["error"]
