"""Tests for CLI entry point."""

from __future__ import annotations

from click.testing import CliRunner

from mcptools.cli import cli


def test_cli_help() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "mcptools" in result.output


def test_cli_version() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.output


def test_inspect_help() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["inspect", "--help"])
    assert result.exit_code == 0
    assert "Inspect" in result.output


def test_doctor_help() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["doctor", "--help"])
    assert result.exit_code == 0
    assert "Diagnose" in result.output


def test_proxy_help() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["proxy", "--help"])
    assert result.exit_code == 0
    assert "proxy" in result.output.lower()


def test_record_help() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["record", "--help"])
    assert result.exit_code == 0


def test_replay_help() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["replay", "--help"])
    assert result.exit_code == 0
