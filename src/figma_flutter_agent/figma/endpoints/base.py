"""Shared Figma connector surface for endpoint mixins."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

from figma_flutter_agent.errors import FigmaApiError


class FigmaEndpointBase:
    """Declares connector methods mixed into ``FigmaConnector`` at runtime."""

    _client: httpx.AsyncClient | None
    _download_semaphore: asyncio.Semaphore

    async def _request(
        self,
        method: str,
        path: str,
        *,
        ok_statuses: set[int] | frozenset[int] = frozenset({200}),
        timeout: httpx.Timeout | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        raise NotImplementedError

    def _require_client(self) -> httpx.AsyncClient:
        raise NotImplementedError

    @staticmethod
    def _rate_limit_error(response: httpx.Response, delay_sec: float) -> FigmaApiError:
        raise NotImplementedError
