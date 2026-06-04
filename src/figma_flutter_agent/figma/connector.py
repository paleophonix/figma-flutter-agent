"""Async Figma REST API client."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from typing import Any

import httpx
from loguru import logger

from figma_flutter_agent.errors import FigmaApiError, sanitize_api_message
from figma_flutter_agent.figma.models import (
    FigmaComponentSetsResponse,
    FigmaComponentsResponse,
    FigmaFileResponse,
    FigmaImagesResponse,
    FigmaNodesResponse,
    FigmaStylesResponse,
)

MAX_RETRIES = 3
BATCH_SIZE = 20
DEFAULT_MAX_CONCURRENT_DOWNLOADS = 8
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
# Figma may return multi-hour Retry-After values when the rate bucket is empty.
# Automatic CLI retries should fail fast instead of blocking for days.
MAX_AUTO_RETRY_DELAY_SEC = 120.0
_UNIX_TIMESTAMP_THRESHOLD = 1_000_000_000.0


def _format_transport_error(exc: httpx.TransportError) -> str:
    """One-line transport failure summary for logs and CLI errors."""
    name = type(exc).__name__
    detail = str(exc).strip()
    return f"{name} ({detail})" if detail else name


def _transport_failure_message(method: str, path: str, exc: httpx.TransportError) -> str:
    """Human-readable Figma API transport error after retries are exhausted."""
    detail = _format_transport_error(exc)
    return (
        f"Could not reach Figma API ({detail}) for {method} {path}. "
        "Check network or VPN, retry later, or use offline mode (--from-dump)."
    )


def merge_figma_nodes_batch(
    target: dict[str, Any],
    batch_nodes: dict[str, Any] | None,
) -> list[str]:
    """Merge a Figma ``nodes`` map into *target*, skipping null entries.

    The REST API may return ``null`` for individual ids (deleted frame, invalid
    id, or ids outside the file). Pydantic cannot model those values.

    Args:
        target: Mutable accumulator for valid node entries.
        batch_nodes: Raw ``nodes`` object from a nodes API response.

    Returns:
        Node ids whose API value was ``null`` (for logging).
    """
    if not isinstance(batch_nodes, dict):
        return []
    dropped: list[str] = []
    for node_id, entry in batch_nodes.items():
        if entry is None:
            dropped.append(node_id)
            continue
        target[node_id] = entry
    return dropped


@dataclass(frozen=True)
class ImageUrlFetchResult:
    """Outcome of batched Figma Images API requests."""

    urls: dict[str, str]
    failed_node_ids: tuple[str, ...]
    rate_limited: bool


class FigmaConnector:
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
        """Parse a ``Retry-After`` header value into seconds to wait."""
        value = raw.strip()
        if not value:
            return None
        try:
            numeric = float(value)
        except ValueError:
            numeric = None
        if numeric is not None:
            if numeric >= _UNIX_TIMESTAMP_THRESHOLD:
                return max(numeric - time.time(), 0.0)
            return max(numeric, 0.0)
        try:
            retry_at = parsedate_to_datetime(value)
            return max(retry_at.timestamp() - time.time(), 0.0)
        except (TypeError, ValueError, OSError):
            return None

    @staticmethod
    def _retry_delay(response: httpx.Response | None, attempt: int) -> float:
        if response is not None:
            retry_after = response.headers.get("Retry-After")
            if retry_after:
                parsed = FigmaConnector._parse_retry_after_seconds(retry_after)
                if parsed is not None:
                    return parsed
        return float(2**attempt)

    @staticmethod
    def _rate_limit_error(response: httpx.Response, delay_sec: float) -> FigmaApiError:
        """Build a descriptive rate-limit error with Figma response headers."""
        retry_after = response.headers.get("Retry-After", "")
        plan_tier = response.headers.get("X-Figma-Plan-Tier", "")
        limit_type = response.headers.get("X-Figma-Rate-Limit-Type", "")
        upgrade_link = response.headers.get("X-Figma-Upgrade-Link", "")
        hours = delay_sec / 3600.0
        message = (
            f"Figma rate limit exceeded (429). Retry-After={retry_after!r} "
            f"({delay_sec:.0f}s, {hours:.1f}h). "
            f"Automatic retry is capped at {MAX_AUTO_RETRY_DELAY_SEC:.0f}s."
        )
        if plan_tier or limit_type:
            message += f" Plan={plan_tier or 'unknown'}, limit={limit_type or 'unknown'}."
        if upgrade_link:
            message += f" Upgrade: {upgrade_link}"
        message += (
            " Wait for the bucket to refill or use a cached dump "
            "(scripts/regen-layout-from-dump.py) to avoid live API calls."
        )
        return FigmaApiError(message, status_code=429)

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

        for attempt in range(MAX_RETRIES):
            try:
                response = await client.request(method, path, timeout=request_timeout, **kwargs)
            except httpx.TransportError as exc:
                last_error = FigmaApiError(_transport_failure_message(method, path, exc))
                if attempt == MAX_RETRIES - 1:
                    raise last_error from exc
                delay = float(2**attempt)
                logger.warning(
                    "Figma {} {} failed ({}) — retry in {:.0f}s ({}/{})",
                    method,
                    path,
                    _format_transport_error(exc),
                    delay,
                    attempt + 2,
                    MAX_RETRIES,
                )
                await asyncio.sleep(delay)
                continue

            if response.status_code in ok_statuses:
                return response

            if response.status_code in _RETRYABLE_STATUS_CODES and attempt < MAX_RETRIES - 1:
                delay = self._retry_delay(response, attempt)
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

            raise FigmaApiError(response.text, status_code=response.status_code)

        if last_error:
            raise last_error
        raise FigmaApiError("Request failed after retries")

    async def fetch_nodes(self, file_key: str, node_ids: list[str]) -> FigmaNodesResponse:
        """Fetch node subtrees for the given file key and node ids."""
        if not node_ids:
            return FigmaNodesResponse()

        merged_nodes: dict[str, Any] = {}
        dropped_node_ids: list[str] = []
        name: str | None = None
        styles: dict[str, dict[str, Any]] | None = None

        for index in range(0, len(node_ids), BATCH_SIZE):
            chunk = node_ids[index : index + BATCH_SIZE]
            ids = ",".join(chunk)
            response = await self._request(
                "GET",
                f"/v1/files/{file_key}/nodes",
                params={"ids": ids},
            )
            payload = response.json()
            if name is None:
                name = payload.get("name")
            batch_styles = payload.get("styles")
            if isinstance(batch_styles, dict):
                styles = {**(styles or {}), **batch_styles}
            dropped_node_ids.extend(
                merge_figma_nodes_batch(merged_nodes, payload.get("nodes"))
            )

        if dropped_node_ids:
            preview = ", ".join(dropped_node_ids[:8])
            suffix = "..." if len(dropped_node_ids) > 8 else ""
            logger.warning(
                "Figma nodes API returned null for {} node(s): {}{}",
                len(dropped_node_ids),
                preview,
                suffix,
            )

        return FigmaNodesResponse.model_validate(
            {"name": name, "nodes": merged_nodes, "styles": styles}
        )

    async def fetch_file(self, file_key: str) -> FigmaFileResponse:
        """Fetch the full Figma file document (Tier 1).

        Args:
            file_key: Figma file key.

        Returns:
            Parsed file payload including ``document``, ``components``, and ``styles``.
        """
        response = await self._request(
            "GET",
            f"/v1/files/{file_key}",
            timeout=httpx.Timeout(180.0, connect=10.0),
        )
        return FigmaFileResponse.model_validate(response.json())

    async def fetch_variables(self, file_key: str) -> dict[str, Any] | None:
        """Fetch local variables when available."""
        response = await self._request(
            "GET",
            f"/v1/files/{file_key}/variables/local",
            ok_statuses={200, 403},
        )
        if response.status_code == 403:
            logger.info("Variables API unavailable, falling back to styles/fills")
            return None
        payload: dict[str, Any] = response.json()
        return payload

    async def fetch_published_variables(self, file_key: str) -> dict[str, Any] | None:
        """Fetch published variables from linked libraries when available."""
        response = await self._request(
            "GET",
            f"/v1/files/{file_key}/variables/published",
            ok_statuses={200, 403, 404},
        )
        if response.status_code != 200:
            logger.info("Published variables API unavailable for file {}", file_key)
            return None
        payload: dict[str, Any] = response.json()
        return payload

    async def fetch_image_fills(self, file_key: str) -> dict[str, str]:
        """Fetch global image fill URLs keyed by ``imageRef``."""
        response = await self._request(
            "GET",
            f"/v1/files/{file_key}/images",
            ok_statuses={200, 403, 404},
        )
        if response.status_code != 200:
            logger.info("Image fills API unavailable for file {}", file_key)
            return {}
        payload: dict[str, Any] = response.json()
        meta = payload.get("meta", {})
        images = meta.get("images") if isinstance(meta, dict) else None
        if not isinstance(images, dict):
            return {}
        return {str(ref): str(url) for ref, url in images.items() if url}

    async def fetch_styles(self, file_key: str) -> dict[str, dict[str, Any]]:
        """Fetch published styles metadata for a file."""
        response = await self._request(
            "GET",
            f"/v1/files/{file_key}/styles",
            ok_statuses={200, 403, 404},
        )
        if response.status_code != 200:
            logger.info("Styles API unavailable for file {}", file_key)
            return {}
        payload = FigmaStylesResponse.model_validate(response.json())
        styles = payload.meta.get("styles")
        if isinstance(styles, dict):
            return styles
        return {}

    async def fetch_components(self, file_key: str) -> dict[str, dict[str, Any]]:
        """Fetch published components metadata for a file."""
        response = await self._request(
            "GET",
            f"/v1/files/{file_key}/components",
            ok_statuses={200, 403, 404},
        )
        if response.status_code != 200:
            logger.info("Components API unavailable for file {}", file_key)
            return {}
        payload = FigmaComponentsResponse.model_validate(response.json())
        components = payload.meta.get("components")
        if isinstance(components, dict):
            return components
        return {}

    async def fetch_component_sets(self, file_key: str) -> dict[str, dict[str, Any]]:
        """Fetch published component set metadata for a file."""
        response = await self._request(
            "GET",
            f"/v1/files/{file_key}/component_sets",
            ok_statuses={200, 403, 404},
        )
        if response.status_code != 200:
            logger.info("Component sets API unavailable for file {}", file_key)
            return {}
        payload = FigmaComponentSetsResponse.model_validate(response.json())
        component_sets = payload.meta.get("component_sets")
        if isinstance(component_sets, dict):
            return component_sets
        return {}

    async def fetch_image_urls(
        self,
        file_key: str,
        node_ids: list[str],
        *,
        fmt: str = "png",
        scale: float = 1.0,
        continue_on_rate_limit: bool = False,
        inter_batch_delay_sec: float = 0.0,
    ) -> ImageUrlFetchResult:
        """Render image URLs for node ids in batches.

        Args:
            file_key: Figma file key.
            node_ids: Node ids to render.
            fmt: Export format (``png`` or ``svg``).
            scale: Raster export scale.
            continue_on_rate_limit: When True, skip batches that hit 429 after retries
                instead of aborting the whole export.
            inter_batch_delay_sec: Pause between batch requests to reduce rate-limit hits.

        Returns:
            Resolved image URLs plus any node ids skipped due to rate limits.
        """
        urls: dict[str, str] = {}
        failed: list[str] = []
        rate_limited = False
        for index in range(0, len(node_ids), BATCH_SIZE):
            if index > 0 and inter_batch_delay_sec > 0:
                await asyncio.sleep(inter_batch_delay_sec)
            batch = node_ids[index : index + BATCH_SIZE]
            try:
                response = await self._request(
                    "GET",
                    f"/v1/images/{file_key}",
                    params={"ids": ",".join(batch), "format": fmt, "scale": scale},
                )
            except FigmaApiError as exc:
                if continue_on_rate_limit and exc.status_code == 429:
                    failed.extend(batch)
                    rate_limited = True
                    logger.warning(
                        "Figma images API rate limit (429); skipping {} node(s) and continuing",
                        len(batch),
                    )
                    await asyncio.sleep(max(inter_batch_delay_sec, 5.0))
                    continue
                raise
            payload = FigmaImagesResponse.model_validate(response.json())
            for node_id, image_url in payload.images.items():
                if image_url:
                    urls[node_id] = image_url
                elif node_id in batch:
                    failed.append(node_id)
        return ImageUrlFetchResult(
            urls=urls,
            failed_node_ids=tuple(dict.fromkeys(failed)),
            rate_limited=rate_limited,
        )

    async def download_bytes(self, url: str) -> bytes:
        """Download binary content from a temporary Figma image URL."""
        async with self._download_semaphore:
            client = self._require_client()
            last_error: Exception | None = None
            for attempt in range(MAX_RETRIES):
                try:
                    response = await client.get(url)
                except httpx.TransportError as exc:
                    last_error = FigmaApiError(
                        _transport_failure_message("GET", url, exc).replace(
                            "Figma API", "asset URL", 1
                        )
                    )
                    if attempt == MAX_RETRIES - 1:
                        raise last_error from exc
                    delay = float(2**attempt)
                    logger.warning(
                        "Asset download failed ({}) — retry in {:.0f}s ({}/{})",
                        _format_transport_error(exc),
                        delay,
                        attempt + 2,
                        MAX_RETRIES,
                    )
                    await asyncio.sleep(delay)
                    continue

                if response.status_code == 200:
                    return response.content

                if response.status_code in _RETRYABLE_STATUS_CODES and attempt < MAX_RETRIES - 1:
                    delay = self._retry_delay(response, attempt)
                    if response.status_code == 429 and delay > MAX_AUTO_RETRY_DELAY_SEC:
                        raise self._rate_limit_error(response, delay)
                    await asyncio.sleep(delay)
                    last_error = FigmaApiError(response.text, status_code=response.status_code)
                    continue

                raise FigmaApiError(response.text, status_code=response.status_code)

            if last_error:
                raise last_error
            raise FigmaApiError("Asset download failed after retries")
