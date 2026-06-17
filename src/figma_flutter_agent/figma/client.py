"""Async Figma REST API client."""

from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx
from loguru import logger

from figma_flutter_agent.errors import FigmaApiError, sanitize_api_message
from figma_flutter_agent.figma.endpoints.images import ImagesEndpoint
from figma_flutter_agent.figma.endpoints.metadata import MetadataEndpoint
from figma_flutter_agent.figma.endpoints.nodes import NodesEndpoint
from figma_flutter_agent.figma.http import (
    format_transport_error,
    parse_retry_after_seconds,
    rate_limit_error,
    retry_delay,
    transport_failure_message,
)
from figma_flutter_agent.figma.limits import (
    DEFAULT_MAX_CONCURRENT_DOWNLOADS,
    MAX_AUTO_RETRY_DELAY_SEC,
    MAX_RETRIES,
    RETRYABLE_STATUS_CODES,
)


class FigmaConnector(NodesEndpoint, MetadataEndpoint, ImagesEndpoint):
    """Fetch design data from the Figma REST API."""

    def __init__(
        self,
        access_token: str,
        base_url: str = "https://api.figma.com",
        *,
        max_concurrent_downloads: int = DEFAULT_MAX_CONCURRENT_DOWNLOADS,
    ) -> None:
        self._access_token = access_token
        self._base_url = base_url.rstrip("/")
        self._client: httpx.AsyncClient | None = None
        self._download_semaphore = asyncio.Semaphore(max_concurrent_downloads)

    async def __aenter__(self) -> FigmaConnector:
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers={"X-Figma-Token": self._access_token},
            timeout=httpx.Timeout(60.0, connect=10.0),
        )
        return self

    async def __aexit__(self, *args: object) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def _require_client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise FigmaApiError("FigmaConnector must be used as an async context manager")
        return self._client

    @staticmethod
    def _parse_retry_after_seconds(raw: str) -> float | None:
        return parse_retry_after_seconds(raw)

    @staticmethod
    def _retry_delay(response: httpx.Response | None, attempt: int) -> float:
        return retry_delay(response, attempt)

    @staticmethod
    def _rate_limit_error(response: httpx.Response, delay_sec: float) -> FigmaApiError:
        return rate_limit_error(response, delay_sec)

    async def _request(
        self,
        method: str,
        path: str,
        *,
        ok_statuses: set[int] | frozenset[int] = frozenset({200}),
        timeout: httpx.Timeout | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        client = self._require_client()
        last_error: Exception | None = None
        request_timeout = timeout or client.timeout
        from figma_flutter_agent.observability.prometheus_metrics import observe_figma_request

        started = time.perf_counter()
        status_code = 0

        for attempt in range(MAX_RETRIES):
            try:
                response = await client.request(method, path, timeout=request_timeout, **kwargs)
            except httpx.TransportError as exc:
                last_error = FigmaApiError(transport_failure_message(method, path, exc))
                if attempt == MAX_RETRIES - 1:
                    raise last_error from exc
                delay = float(2**attempt)
                logger.warning(
                    "Figma {} {} failed ({}) — retry in {:.0f}s ({}/{})",
                    method,
                    path,
                    format_transport_error(exc),
                    delay,
                    attempt + 2,
                    MAX_RETRIES,
                )
                await asyncio.sleep(delay)
                continue

            if response.status_code in ok_statuses:
                status_code = response.status_code
                observe_figma_request(path, status_code, time.perf_counter() - started)
                return response

            status_code = response.status_code
            if response.status_code in RETRYABLE_STATUS_CODES and attempt < MAX_RETRIES - 1:
                delay = retry_delay(response, attempt)
                if response.status_code == 429 and delay > MAX_AUTO_RETRY_DELAY_SEC:
                    raise self._rate_limit_error(response, delay)
                body_hint = sanitize_api_message(response.text or "")
                logger.warning(
                    "Figma {} {} returned HTTP {}: {} — retry in {:.1f}s ({}/{})",
                    method,
                    path,
                    response.status_code,
                    body_hint or "(empty body)",
                    delay,
                    attempt + 2,
                    MAX_RETRIES,
                )
                await asyncio.sleep(delay)
                last_error = FigmaApiError(response.text, status_code=response.status_code)
                continue

            observe_figma_request(path, response.status_code, time.perf_counter() - started)
            raise FigmaApiError(response.text, status_code=response.status_code)

        if last_error:
            if status_code:
                observe_figma_request(path, status_code, time.perf_counter() - started)
            raise last_error
        raise FigmaApiError("Request failed after retries")
