"""Minimal async client for local ``opencode serve``."""

from __future__ import annotations

import asyncio
import base64
from collections.abc import Callable
from typing import Any, cast
from urllib.parse import urlparse

import httpx
from loguru import logger

from figma_flutter_agent.dev.opencode.opencode_policy import split_opencode_model
from figma_flutter_agent.dev.opencode.opencode_session_progress import (
    OPENCODE_PROGRESS_POLL_SEC,
    normalize_session_messages,
    summarize_opencode_progress,
)
from figma_flutter_agent.errors import FigmaFlutterError

DEFAULT_OPENCODE_PROMPT_TIMEOUT_SEC = 600.0


class OpenCodeClient:
    """Thin HTTP client for OpenCode session API."""

    def __init__(
        self,
        *,
        base_url: str,
        username: str = "opencode",
        password: str = "",
        worktree_directory: str | None = None,
        timeout_sec: float = DEFAULT_OPENCODE_PROMPT_TIMEOUT_SEC,
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
            token = base64.b64encode(f"{self._username}:{self._password}".encode()).decode("ascii")
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

    async def list_session_messages(self, session_id: str) -> list[dict[str, Any]]:
        """GET /session/{id}/message transcript (may update while a prompt runs)."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self._base_url}/session/{session_id}/message",
                headers=self._headers(),
                params=self._params(),
            )
            response.raise_for_status()
            return normalize_session_messages(response.json())

    async def prompt_message(
        self,
        session_id: str,
        *,
        text: str,
        agent: str | None = None,
        model: str | None = None,
        reasoning_effort: str | None = None,
        on_progress: Callable[[str], None] | None = None,
        progress_step: str = "repair",
        progress_poll_sec: float = OPENCODE_PROGRESS_POLL_SEC,
    ) -> dict[str, Any]:
        """POST /session/{id}/message (sync, long-running).

        When ``on_progress`` is set, poll the session transcript while the prompt
        request is in flight and emit short progress summaries.
        """
        if on_progress is None:
            return await self._prompt_message_blocking(
                session_id,
                text=text,
                agent=agent,
                model=model,
                reasoning_effort=reasoning_effort,
            )
        return await self._prompt_message_with_progress_poll(
            session_id,
            text=text,
            agent=agent,
            model=model,
            reasoning_effort=reasoning_effort,
            on_progress=on_progress,
            progress_step=progress_step,
            progress_poll_sec=progress_poll_sec,
        )

    async def _prompt_message_blocking(
        self,
        session_id: str,
        *,
        text: str,
        agent: str | None = None,
        model: str | None = None,
        reasoning_effort: str | None = None,
    ) -> dict[str, Any]:
        """POST /session/{id}/message without progress polling."""
        body: dict[str, Any] = {"parts": [{"type": "text", "text": text}]}
        if agent:
            body["agent"] = agent
        if model:
            provider_id, model_id = split_opencode_model(model)
            body["model"] = {"providerID": provider_id, "modelID": model_id}
        if reasoning_effort:
            body["reasoningEffort"] = reasoning_effort
        logger.info(
            "OpenCode prompt_message dispatch session={} agent={} model={} chars={} timeout_sec={}",
            session_id,
            agent,
            model,
            len(text),
            self._timeout,
        )
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    f"{self._base_url}/session/{session_id}/message",
                    headers=self._headers(),
                    params=self._params(),
                    json=body,
                )
                response.raise_for_status()
                payload = cast(dict[str, Any], response.json())
        except httpx.TimeoutException as exc:
            logger.error(
                "OpenCode prompt_message timed out after {}s session={} agent={} model={}",
                self._timeout,
                session_id,
                agent,
                model,
            )
            raise FigmaFlutterError(
                f"OpenCode repair prompt timed out after {self._timeout:.0f}s "
                f"(session={session_id}). Restart OpenCode serve and retry, or lower "
                "debug_pipeline.loops.opencode_prompt_timeout_sec."
            ) from exc
        logger.info(
            "OpenCode prompt_message completed session={} agent={}",
            session_id,
            agent,
        )
        return payload

    async def _prompt_message_with_progress_poll(
        self,
        session_id: str,
        *,
        text: str,
        agent: str | None = None,
        model: str | None = None,
        reasoning_effort: str | None = None,
        on_progress: Callable[[str], None],
        progress_step: str,
        progress_poll_sec: float,
    ) -> dict[str, Any]:
        """Run blocking prompt while polling session messages for live progress."""
        prompt_task = asyncio.create_task(
            self._prompt_message_blocking(
                session_id,
                text=text,
                agent=agent,
                model=model,
                reasoning_effort=reasoning_effort,
            )
        )
        last_line = ""
        while not prompt_task.done():
            try:
                await asyncio.wait_for(asyncio.shield(prompt_task), timeout=progress_poll_sec)
            except TimeoutError:
                try:
                    messages = await self.list_session_messages(session_id)
                    line = summarize_opencode_progress(messages)
                except Exception as exc:
                    line = f"polling: {exc.__class__.__name__}"
                if line and line != last_line:
                    last_line = line
                    on_progress(line)
        result = prompt_task.result()
        if last_line:
            on_progress(last_line)
        return result

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


def parse_serve_host_port(base_url: str) -> tuple[str, int]:
    """Return hostname and port from an OpenCode base URL."""
    parsed = urlparse(base_url)
    host = parsed.hostname or "127.0.0.1"
    if parsed.port is not None:
        return host, parsed.port
    return host, 443 if parsed.scheme == "https" else 4096
