"""Transport layer for MCP proxy — handles stdio and SSE communication."""

from __future__ import annotations

import asyncio
import json
import sys
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel


class McpMessage(BaseModel):
    """A captured MCP message (JSON-RPC 2.0)."""

    timestamp: float
    direction: str  # "client_to_server" or "server_to_client"
    data: dict[str, Any]

    @property
    def method(self) -> str | None:
        return self.data.get("method")

    @property
    def msg_id(self) -> int | str | None:
        return self.data.get("id")

    @property
    def is_request(self) -> bool:
        return "method" in self.data

    @property
    def is_response(self) -> bool:
        return "result" in self.data or "error" in self.data

    @property
    def is_error(self) -> bool:
        return "error" in self.data

    @property
    def error_message(self) -> str | None:
        error = self.data.get("error")
        if isinstance(error, dict):
            return error.get("message", str(error))
        return str(error) if error else None


@dataclass
class StdioTransport:
    """Manages stdio communication with an MCP server subprocess."""

    command: list[str]
    env: dict[str, str] = field(default_factory=dict)
    process: asyncio.subprocess.Process | None = None

    async def start(self) -> None:
        """Start the subprocess."""
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
        """Send a JSON-RPC message to the server."""
        if self.process is None or self.process.stdin is None:
            raise RuntimeError("Transport not started")

        line = json.dumps(data) + "\n"
        self.process.stdin.write(line.encode())
        await self.process.stdin.drain()

    async def receive(self) -> dict[str, Any] | None:
        """Read a JSON-RPC message from the server. Returns None on EOF."""
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
        """Read a line from stderr (for diagnostics). Returns None on EOF."""
        if self.process is None or self.process.stderr is None:
            return None

        line = await self.process.stderr.readline()
        if not line:
            return None
        return line.decode().strip()

    async def stop(self) -> None:
        """Stop the subprocess."""
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
        return self.process is not None and self.process.returncode is None


class StdinReader:
    """Read JSON-RPC messages from our own stdin (client side)."""

    def __init__(self) -> None:
        self._reader: asyncio.StreamReader | None = None

    async def start(self) -> None:
        loop = asyncio.get_event_loop()
        self._reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(self._reader)
        await loop.connect_read_pipe(lambda: protocol, sys.stdin)

    async def receive(self) -> dict[str, Any] | None:
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
    """Write JSON-RPC messages to our own stdout (back to client)."""

    def send_sync(self, data: dict[str, Any]) -> None:
        line = json.dumps(data) + "\n"
        sys.stdout.write(line)
        sys.stdout.flush()
