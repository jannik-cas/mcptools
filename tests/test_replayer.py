"""Tests for session replayer."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mcptools.record.replayer import run_replayer


@pytest.fixture
def sample_session(tmp_path: Path) -> Path:
    session = {
        "mcptools_version": "0.1.0",
        "recorded_at": 1000.0,
        "duration": 5.0,
        "message_count": 3,
        "messages": [
            {
                "timestamp": 1000.0,
                "relative_time": 0.0,
                "direction": "client_to_server",
                "data": {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            },
            {
                "timestamp": 1000.5,
                "relative_time": 0.5,
                "direction": "server_to_client",
                "data": {"jsonrpc": "2.0", "id": 1, "result": {}, "_latency_ms": 500},
            },
            {
                "timestamp": 1001.0,
                "relative_time": 1.0,
                "direction": "client_to_server",
                "data": {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            },
        ],
    }
    path = tmp_path / "session.json"
    path.write_text(json.dumps(session))
    return path


@pytest.mark.asyncio
async def test_replay_session(sample_session: Path) -> None:
    # Should complete without error
    await run_replayer(sample_session, speed=0)  # speed=0 skips delays


@pytest.mark.asyncio
async def test_replay_with_filter(sample_session: Path) -> None:
    await run_replayer(sample_session, speed=0, filter_method="tools/*")


@pytest.mark.asyncio
async def test_replay_empty_session(tmp_path: Path) -> None:
    session = {
        "mcptools_version": "0.1.0",
        "recorded_at": 1000.0,
        "duration": 0,
        "message_count": 0,
        "messages": [],
    }
    path = tmp_path / "empty.json"
    path.write_text(json.dumps(session))

    await run_replayer(path, speed=0)
