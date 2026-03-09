"""Transport layer for MCP proxy — handles stdio and SSE communication.

Provides the low-level primitives for reading and writing newline-
delimited JSON-RPC messages over subprocess stdio pipes or the
process's own stdin/stdout.
"""

from __future__ import annotations

import asyncio
import json
import sys
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel


class McpMessage(BaseModel):
    """A captured MCP message (JSON-RPC 2.0).

    Wraps the raw JSON-RPC data together with a timestamp and
    direction label so that proxy / recording layers can reason about
    message flow.

    Attributes:
        timestamp: Epoch time when the message was captured.
        direction: ``"client_to_server"`` or ``"server_to_client"``.
        data: The raw JSON-RPC message dict.
    """

    timestamp: float
    direction: str  # "client_to_server" or "server_to_client"
    data: dict[str, Any]

    @property
    def method(self) -> str | None:
        """JSON-RPC method name, or *None* for responses."""
        return self.data.get("method")

    @property
    def msg_id(self) -> int | str | None:
        """JSON-RPC message ``id``, or *None* for notifications."""
        return self.data.get("id")

    @property
    def is_request(self) -> bool:
        """``True`` if the message contains a ``method`` field."""
        return "method" in self.data

    @property
    def is_response(self) -> bool:
        """``True`` if the message is a response (has ``result`` or ``error``)."""
        return "result" in self.data or "error" in self.data

    @property
    def is_error(self) -> bool:
        """``True`` if the message is an error response."""
        return "error" in self.data

    @property
    def error_message(self) -> str | None:
        """Human-readable error string, or *None* if not an error."""
        error = self.data.get("error")
        if isinstance(error, dict):
            return error.get("message", str(error))
        return str(error) if error else None


@dataclass
class StdioTransport:
    """Manages stdio communication with an MCP server subprocess.

    Launches the server as a child process and provides async
    methods to exchange newline-delimited JSON-RPC messages.

    Attributes:
        command: The command and arguments to launch the server.
        env: Extra environment variables injected into the subprocess.
        process: The running subprocess, or *None* before :meth:`start`.
    """

    command: list[str]
    env: dict[str, str] = field(default_factory=dict)
    process: asyncio.subprocess.Process | None = None

    async def start(self) -> None:
        """Start the server subprocess."""
        import os

        full_env = {**os.environ, **self.env}
        self.process = await asyncio.create_subprocess_exec(
            *self.command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=full_env,
        )

    async def send(self, data: dict[str, Any]) -> None:
        """Send a JSON-RPC message to the server.

        Args:
            data: Message dict to serialise and write.

        Raises:
            RuntimeError: If the transport has not been started.
        """
        if self.process is None or self.process.stdin is None:
            raise RuntimeError("Transport not started")

        line = json.dumps(data) + "\n"
        self.process.stdin.write(line.encode())
        await self.process.stdin.drain()

    async def receive(self) -> dict[str, Any] | None:
        """Read a JSON-RPC message from the server.

        Returns:
            Parsed message dict, or *None* on EOF.

        Raises:
            RuntimeError: If the transport has not been started.
        """
        if self.process is None or self.process.stdout is None:
            raise RuntimeError("Transport not started")

        while True:
            line = await self.process.stdout.readline()
            if not line:
                return None

            text = line.decode().strip()
            if not text:
                return None

            try:
                return json.loads(text)
            except json.JSONDecodeError:
                print(
                    f"Warning: skipping malformed JSON from server: {text[:200]}",
                    file=sys.stderr,
                )
                continue

    async def read_stderr(self) -> str | None:
        """Read a line from stderr (for diagnostics).

        Returns:
            Decoded line, or *None* on EOF.
        """
        if self.process is None or self.process.stderr is None:
            return None

        line = await self.process.stderr.readline()
        if not line:
            return None
        return line.decode().strip()

    async def stop(self) -> None:
        """Terminate the server subprocess gracefully."""
        if self.process is not None:
            try:
                self.process.terminate()
                await asyncio.wait_for(self.process.wait(), timeout=5)
            except (asyncio.TimeoutError, ProcessLookupError):
                try:
                    self.process.kill()
                except ProcessLookupError:
                    pass

    @property
    def is_running(self) -> bool:
        """``True`` if the subprocess is still alive."""
        return self.process is not None and self.process.returncode is None


class StdinReader:
    """Read JSON-RPC messages from the process's own stdin (client side).

    Used by the proxy to receive messages from the MCP client that
    launched the proxy process.
    """

    def __init__(self) -> None:
        self._reader: asyncio.StreamReader | None = None

    async def start(self) -> None:
        """Connect an async reader to ``sys.stdin``."""
        loop = asyncio.get_event_loop()
        self._reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(self._reader)
        await loop.connect_read_pipe(lambda: protocol, sys.stdin)

    async def receive(self) -> dict[str, Any] | None:
        """Read the next JSON-RPC message from stdin.

        Returns:
            Parsed message dict, or *None* on EOF.

        Raises:
            RuntimeError: If the reader has not been started.
        """
        if self._reader is None:
            raise RuntimeError("Reader not started")

        while True:
            line = await self._reader.readline()
            if not line:
                return None

            text = line.decode().strip()
            if not text:
                return None

            try:
                return json.loads(text)
            except json.JSONDecodeError:
                print(
                    f"Warning: skipping malformed JSON from client: {text[:200]}",
                    file=sys.stderr,
                )
                continue


class StdoutWriter:
    """Write JSON-RPC messages to the process's own stdout (back to client)."""

    def send_sync(self, data: dict[str, Any]) -> None:
        """Serialise and write a message to stdout.

        Args:
            data: Message dict to send.
        """
        line = json.dumps(data) + "\n"
        sys.stdout.write(line)
        sys.stdout.flush()
