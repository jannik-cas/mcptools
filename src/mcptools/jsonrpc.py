"""Shared JSON-RPC 2.0 helpers for MCP communication.

Provides a sequential ID generator and a request-builder used by every
module that speaks the MCP protocol.
"""

from __future__ import annotations

from typing import Any


class IdGenerator:
    """Sequential JSON-RPC message ID generator.

    Each call to :meth:`next` returns a monotonically increasing
    integer suitable for use as a JSON-RPC ``id`` field.

    Args:
        start: Initial counter value (first ID returned is ``start + 1``).
    """

    def __init__(self, start: int = 0) -> None:
        self._next_id = start

    def next(self) -> int:
        """Return the next unique message ID.

        Returns:
            An integer one greater than the previous call.
        """
        self._next_id += 1
        return self._next_id


def make_request(
    method: str,
    params: dict[str, Any] | None = None,
    msg_id: int | None = None,
) -> dict[str, Any]:
    """Build a JSON-RPC 2.0 request (or notification) message.

    When *msg_id* is ``None`` the result is a JSON-RPC *notification*
    (no ``id`` field).  Otherwise it is a full request.

    Args:
        method: The JSON-RPC method name (e.g. ``"initialize"``).
        params: Optional parameters dict to include in the message.
        msg_id: Optional message ID.  Omit for notifications.

    Returns:
        A dict ready to be serialised as JSON and sent over the wire.
    """
    msg: dict[str, Any] = {
        "jsonrpc": "2.0",
        "method": method,
    }
    if msg_id is not None:
        msg["id"] = msg_id
    if params is not None:
        msg["params"] = params
    return msg
