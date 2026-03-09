"""Tests for config parsing."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mcptools.config.parser import parse_config


@pytest.fixture
def tmp_config(tmp_path: Path) -> Path:
    config = {
        "mcpServers": {
            "filesystem": {
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
            },
            "github": {
                "command": "uvx",
                "args": ["mcp-server-github"],
                "env": {
                    "GITHUB_TOKEN": "test-token",
                },
            },
        }
    }
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config))
    return config_path


def test_parse_config_servers(tmp_config: Path) -> None:
    config = parse_config(tmp_config)
    assert len(config.servers) == 2
    assert "filesystem" in config.servers
    assert "github" in config.servers


def test_parse_config_server_details(tmp_config: Path) -> None:
    config = parse_config(tmp_config)
    fs = config.servers["filesystem"]
    assert fs.command == "npx"
    assert fs.args == ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]
    assert fs.transport == "stdio"


def test_parse_config_env(tmp_config: Path) -> None:
    config = parse_config(tmp_config)
    gh = config.servers["github"]
    assert gh.env == {"GITHUB_TOKEN": "test-token"}


def test_parse_config_sse_transport(tmp_path: Path) -> None:
    config = {
        "mcpServers": {
            "remote": {
                "command": "",
                "url": "http://localhost:8080/sse",
            }
        }
    }
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config))

    result = parse_config(config_path)
    assert result.servers["remote"].transport == "sse"
    assert result.servers["remote"].url == "http://localhost:8080/sse"


def test_parse_empty_config(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text("{}")

    result = parse_config(config_path)
    assert len(result.servers) == 0
