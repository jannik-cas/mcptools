"""Tests for recorder save/load roundtrip."""

from __future__ import annotations

import json
from pathlib import Path

from mcptools.proxy.transport import McpMessage
from mcptools.record.recorder import SessionRecorder


def test_recorder_save_creates_valid_json(tmp_path: Path) -> None:
    """Recording and saving should produce valid JSON with expected structure."""
    output = tmp_path / "test_session.json"
    recorder = SessionRecorder(output)

    # Simulate recording messages
    recorder.on_message(
        McpMessage(
            timestamp=1000.0,
            direction="client_to_server",
            data={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        )
    )
    recorder.on_message(
        McpMessage(
            timestamp=1000.5,
            direction="server_to_client",
            data={"jsonrpc": "2.0", "id": 1, "result": {"capabilities": {}}},
        )
    )

    recorder.save()

    # Verify file exists and is valid JSON
    assert output.exists()
    session = json.loads(output.read_text())

    assert session["mcptools_version"] == "0.1.0"
    assert session["message_count"] == 2
    assert len(session["messages"]) == 2
    assert "recorded_at" in session
    assert "duration" in session


def test_recorder_message_structure(tmp_path: Path) -> None:
    """Recorded messages should preserve direction and data."""
    output = tmp_path / "test_session.json"
    recorder = SessionRecorder(output)

    recorder.on_message(
        McpMessage(
            timestamp=1000.0,
            direction="client_to_server",
            data={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
        )
    )

    recorder.save()
    session = json.loads(output.read_text())

    msg = session["messages"][0]
    assert msg["direction"] == "client_to_server"
    assert msg["data"]["method"] == "tools/list"
    assert "relative_time" in msg
    assert "timestamp" in msg


def test_recorder_empty_session(tmp_path: Path) -> None:
    """Empty session should still save valid JSON."""
    output = tmp_path / "empty.json"
    recorder = SessionRecorder(output)
    recorder.save()

    session = json.loads(output.read_text())
    assert session["message_count"] == 0
    assert session["messages"] == []
