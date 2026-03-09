"""Tests for transport layer."""

from __future__ import annotations

from mcptools.proxy.transport import McpMessage


def test_mcp_message_request() -> None:
    msg = McpMessage(
        timestamp=1000.0,
        direction="client_to_server",
        data={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
    )
    assert msg.is_request
    assert not msg.is_response
    assert not msg.is_error
    assert msg.method == "tools/list"
    assert msg.msg_id == 1


def test_mcp_message_response() -> None:
    msg = McpMessage(
        timestamp=1000.0,
        direction="server_to_client",
        data={"jsonrpc": "2.0", "id": 1, "result": {"tools": []}},
    )
    assert not msg.is_request
    assert msg.is_response
    assert not msg.is_error
    assert msg.msg_id == 1


def test_mcp_message_error() -> None:
    msg = McpMessage(
        timestamp=1000.0,
        direction="server_to_client",
        data={
            "jsonrpc": "2.0",
            "id": 1,
            "error": {"code": -32600, "message": "Invalid request"},
        },
    )
    assert msg.is_error
    assert msg.error_message == "Invalid request"


def test_mcp_message_notification() -> None:
    msg = McpMessage(
        timestamp=1000.0,
        direction="client_to_server",
        data={"jsonrpc": "2.0", "method": "notifications/initialized"},
    )
    assert msg.is_request
    assert msg.msg_id is None
    assert msg.method == "notifications/initialized"
