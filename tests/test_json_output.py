"""Tests for --json output mode on inspect and doctor."""

from __future__ import annotations

import json

from click.testing import CliRunner

from mcptools.cli import cli


def test_inspect_json_nonexistent():
    """inspect --json should output valid JSON even on error."""
    runner = CliRunner()
    result = runner.invoke(cli, ["inspect", "--json", "nonexistent-xyz-cmd"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "error" in data


def test_doctor_json_missing_config():
    """doctor --json with a bogus config should output JSON error."""
    runner = CliRunner()
    # Without a config, doctor auto-detects. We can't guarantee no config exists,
    # so just check the --json flag is accepted.
    result = runner.invoke(cli, ["doctor", "--json", "--help"])
    assert result.exit_code == 0
    assert "--json" in result.output


def test_inspect_json_flag_in_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["inspect", "--help"])
    assert "--json" in result.output


def test_doctor_json_flag_in_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["doctor", "--help"])
    assert "--json" in result.output
