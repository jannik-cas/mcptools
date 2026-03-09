"""Tests for shared JSON-RPC helpers."""

from __future__ import annotations

from mcptools.jsonrpc import IdGenerator, make_request


def test_id_generator_starts_at_zero() -> None:
    gen = IdGenerator()
    assert gen.next() == 1
    assert gen.next() == 2
    assert gen.next() == 3


def test_id_generator_custom_start() -> None:
    gen = IdGenerator(start=10)
    assert gen.next() == 11


def test_make_request_basic() -> None:
    msg = make_request("tools/list", msg_id=1)
    assert msg == {"jsonrpc": "2.0", "method": "tools/list", "id": 1}


def test_make_request_with_params() -> None:
    msg = make_request("initialize", {"protocolVersion": "2024-11-05"}, msg_id=1)
    assert msg["method"] == "initialize"
    assert msg["params"] == {"protocolVersion": "2024-11-05"}
    assert msg["id"] == 1


def test_make_request_notification() -> None:
    """Notifications have no id."""
    msg = make_request("notifications/initialized")
    assert "id" not in msg
    assert msg["method"] == "notifications/initialized"


def test_make_request_no_params_omitted() -> None:
    msg = make_request("tools/list", msg_id=5)
    assert "params" not in msg
