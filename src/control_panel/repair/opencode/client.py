"""OpenCode HTTP client for headless repair stages."""

from __future__ import annotations

import base64
from typing import Any, cast

import httpx
from loguru import logger

from figma_flutter_agent.dev.opencode.opencode_policy import split_opencode_model
from figma_flutter_agent.errors import FigmaFlutterError


class OpenCodeClient:
    """Minimal async client for ``opencode serve`` session API."""

    def __init__(
        self,
        *,
        base_url: str,
        username: str = "opencode",
        password: str = "",
        worktree_directory: str | None = None,
        timeout_sec: float = 3600.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._username = username
        self._password = password
        self._directory = worktree_directory
        self._timeout = timeout_sec

    def bind_worktree(self, directory: str | None) -> None:
        """Point subsequent requests at a git worktree directory."""
        self._directory = directory

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._directory:
            headers["x-opencode-directory"] = self._directory
        if self._password:
            token = base64.b64encode(f"{self._username}:{self._password}".encode()).decode(
                "ascii"
            )
            headers["Authorization"] = f"Basic {token}"
        return headers

    def _params(self) -> dict[str, str]:
        if self._directory:
            return {"directory": self._directory}
        return {}

    async def health(self) -> dict[str, Any]:
        """GET /global/health."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self._base_url}/global/health",
                headers=self._headers(),
                params=self._params(),
            )
            response.raise_for_status()
            return cast(dict[str, Any], response.json())

    async def create_session(self, *, title: str, parent_id: str | None = None) -> str:
        """POST /session and return session id."""
        body: dict[str, Any] = {"title": title}
        if parent_id:
            body["parentID"] = parent_id
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self._base_url}/session",
                headers=self._headers(),
                params=self._params(),
                json=body,
            )
            response.raise_for_status()
            data = response.json()
        session_id = str(data.get("id") or data.get("sessionID") or "")
        if not session_id:
            raise FigmaFlutterError("OpenCode session create returned no id")
        return session_id

    async def prompt_message(
        self,
        session_id: str,
        *,
        text: str,
        agent: str | None = None,
        model: str | None = None,
        reasoning_effort: str | None = None,
    ) -> dict[str, Any]:
        """POST /session/{id}/message (sync, long-running)."""
        body: dict[str, Any] = {"parts": [{"type": "text", "text": text}]}
        if agent:
            body["agent"] = agent
        if model:
            provider_id, model_id = split_opencode_model(model)
            body["model"] = {"providerID": provider_id, "modelID": model_id}
        if reasoning_effort:
            body["reasoningEffort"] = reasoning_effort
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                f"{self._base_url}/session/{session_id}/message",
                headers=self._headers(),
                params=self._params(),
                json=body,
            )
            response.raise_for_status()
            return cast(dict[str, Any], response.json())

    async def prompt_async(
        self,
        session_id: str,
        *,
        text: str,
        agent: str | None = None,
    ) -> None:
        """POST /session/{id}/prompt_async (fire-and-forget)."""
        body: dict[str, Any] = {"parts": [{"type": "text", "text": text}]}
        if agent:
            body["agent"] = agent
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self._base_url}/session/{session_id}/prompt_async",
                headers=self._headers(),
                params=self._params(),
                json=body,
            )
            response.raise_for_status()

    async def session_diff(self, session_id: str) -> list[dict[str, Any]]:
        """GET /session/{id}/diff."""
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.get(
                f"{self._base_url}/session/{session_id}/diff",
                headers=self._headers(),
                params=self._params(),
            )
            response.raise_for_status()
            data = response.json()
        if isinstance(data, list):
            return data
        return []

    async def abort_session(self, session_id: str) -> None:
        """POST /session/{id}/abort."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self._base_url}/session/{session_id}/abort",
                headers=self._headers(),
                params=self._params(),
            )
            if response.status_code >= 400:
                logger.warning("OpenCode abort failed: {}", response.text[:200])
