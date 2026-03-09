"""Shared JSON-RPC 2.0 helpers for MCP communication."""

from __future__ import annotations

from typing import Any


class IdGenerator:
    """Thread-safe JSON-RPC message ID generator."""

    def __init__(self, start: int = 0) -> None:
        self._next_id = start

    def next(self) -> int:
        self._next_id += 1
        return self._next_id


def make_request(
    method: str,
    params: dict[str, Any] | None = None,
    msg_id: int | None = None,
) -> dict[str, Any]:
    """Build a JSON-RPC 2.0 request message."""
    msg: dict[str, Any] = {
        "jsonrpc": "2.0",
        "method": method,
    }
    if msg_id is not None:
        msg["id"] = msg_id
    if params is not None:
        msg["params"] = params
    return msg
