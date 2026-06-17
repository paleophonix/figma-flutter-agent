"""Transport abstraction for OpenCode prompt delivery."""

from __future__ import annotations

from typing import Any, Protocol

from control_panel.repair.opencode.client import OpenCodeClient


class RepairTransport(Protocol):
    """Send a prompt to an OpenCode session."""

    async def send(
        self,
        session_id: str,
        *,
        text: str,
        agent: str | None = None,
        model: str | None = None,
    ) -> dict[str, Any]:
        """Deliver prompt and return response payload."""
        ...


class SyncMessageTransport:
    """MVP default: blocking POST /session/{id}/message."""

    def __init__(self, client: OpenCodeClient) -> None:
        self._client = client

    async def send(
        self,
        session_id: str,
        *,
        text: str,
        agent: str | None = None,
        model: str | None = None,
    ) -> dict[str, Any]:
        return await self._client.prompt_message(
            session_id,
            text=text,
            agent=agent,
            model=model,
        )


class AsyncPromptTransport:
    """Optional: fire-and-forget prompt_async (progress via external SSE)."""

    def __init__(self, client: OpenCodeClient) -> None:
        self._client = client

    async def send(
        self,
        session_id: str,
        *,
        text: str,
        agent: str | None = None,
        model: str | None = None,
    ) -> dict[str, Any]:
        await self._client.prompt_async(session_id, text=text, agent=agent)
        return {"async": True, "model": model}
