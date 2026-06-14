"""Minimal synchronous JSON WebSocket client for local debug services."""

from __future__ import annotations

import base64
import contextlib
import json
import os
import socket
import struct
from typing import Any
from urllib.parse import urlparse


class JsonWebSocket:
    """Blocking JSON-RPC WebSocket client for localhost VM Service / CDP."""

    def __init__(self, url: str, *, timeout_sec: float = 5.0) -> None:
        parsed = urlparse(url)
        if parsed.scheme not in {"ws", "wss"}:
            msg = f"Unsupported WebSocket scheme: {parsed.scheme}"
            raise ValueError(msg)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or (443 if parsed.scheme == "wss" else 80)
        path = parsed.path or "/"
        if parsed.query:
            path = f"{path}?{parsed.query}"

        self._sock = socket.create_connection((host, port), timeout=timeout_sec)
        self._sock.settimeout(timeout_sec)
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        request = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {host}:{port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n"
            "\r\n"
        )
        self._sock.sendall(request.encode("ascii"))
        response = self._read_http_headers()
        if " 101 " not in response:
            msg = f"WebSocket upgrade failed: {response.splitlines()[0] if response else 'empty'}"
            raise ConnectionError(msg)

    def close(self) -> None:
        with contextlib.suppress(OSError):
            self._sock.close()

    def send_json(self, payload: dict[str, Any]) -> None:
        self._send_text(json.dumps(payload, separators=(",", ":")))

    def recv_json(self) -> dict[str, Any] | None:
        frame = self._recv_frame()
        if frame is None:
            return None
        return json.loads(frame)

    def _read_http_headers(self) -> str:
        buffer = bytearray()
        while b"\r\n\r\n" not in buffer:
            chunk = self._sock.recv(4096)
            if not chunk:
                break
            buffer.extend(chunk)
        return buffer.decode("iso-8859-1", errors="replace")

    def _send_text(self, payload: str) -> None:
        data = payload.encode("utf-8")
        mask = os.urandom(4)
        masked = bytes(byte ^ mask[index % 4] for index, byte in enumerate(data))
        header = bytearray([0x81])
        length = len(data)
        if length < 126:
            header.append(0x80 | length)
        elif length < (1 << 16):
            header.append(0x80 | 126)
            header.extend(struct.pack("!H", length))
        else:
            header.append(0x80 | 127)
            header.extend(struct.pack("!Q", length))
        header.extend(mask)
        header.extend(masked)
        self._sock.sendall(header)

    def _recv_frame(self) -> str | None:
        first = self._sock.recv(2)
        if not first:
            return None
        if len(first) < 2:
            extra = self._sock.recv(2 - len(first))
            first += extra
        byte1, byte2 = first[0], first[1]
        opcode = byte1 & 0x0F
        if opcode == 0x8:
            return None
        masked = bool(byte2 & 0x80)
        length = byte2 & 0x7F
        if length == 126:
            length = struct.unpack("!H", self._read_exact(2))[0]
        elif length == 127:
            length = struct.unpack("!Q", self._read_exact(8))[0]
        mask = self._read_exact(4) if masked else b""
        payload = self._read_exact(length)
        if masked:
            payload = bytes(
                byte ^ mask[index % 4] for index, byte in enumerate(payload)
            )
        if opcode == 0x1:
            return payload.decode("utf-8", errors="replace")
        return None

    def _read_exact(self, size: int) -> bytes:
        chunks: list[bytes] = []
        remaining = size
        while remaining > 0:
            chunk = self._sock.recv(remaining)
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)
