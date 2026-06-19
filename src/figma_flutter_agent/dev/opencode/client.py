"""Minimal async client for local ``opencode serve``."""

from __future__ import annotations

import base64
from typing import Any, cast
from urllib.parse import urlparse

import httpx

from figma_flutter_agent.errors import FigmaFlutterError


class OpenCodeClient:
    """Thin HTTP client for OpenCode session API."""

    def __init__(
        self,
        *,
        base_url: str,
        username: str = "opencode",
        password: str = "",
        timeout_sec: float = 30.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._username = username
        self._password = password
        self._timeout = timeout_sec

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._password:
            token = base64.b64encode(f"{self._username}:{self._password}".encode()).decode(
                "ascii"
            )
            headers["Authorization"] = f"Basic {token}"
        return headers

    async def health(self) -> dict[str, Any]:
        """GET /global/health."""
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.get(
                f"{self._base_url}/global/health",
                headers=self._headers(),
            )
            response.raise_for_status()
            return cast(dict[str, Any], response.json())

    async def create_session(self, *, title: str) -> str:
        """POST /session and return session id."""
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                f"{self._base_url}/session",
                headers=self._headers(),
                json={"title": title},
            )
            response.raise_for_status()
            data = response.json()
        session_id = str(data.get("id") or data.get("sessionID") or "")
        if not session_id:
            raise FigmaFlutterError("OpenCode session create returned no id")
        return session_id


def parse_serve_host_port(base_url: str) -> tuple[str, int]:
    """Return hostname and port from an OpenCode base URL."""
    parsed = urlparse(base_url)
    host = parsed.hostname or "127.0.0.1"
    if parsed.port is not None:
        return host, parsed.port
    return host, 443 if parsed.scheme == "https" else 4096
