"""Figma image endpoint methods."""

from __future__ import annotations

import asyncio

import httpx
from loguru import logger

from figma_flutter_agent.errors import FigmaApiError
from figma_flutter_agent.figma.endpoints.base import FigmaEndpointBase
from figma_flutter_agent.figma.http import (
    format_transport_error,
    retry_delay,
    transport_failure_message,
)
from figma_flutter_agent.figma.images import ImageUrlFetchResult
from figma_flutter_agent.figma.limits import (
    BATCH_SIZE,
    MAX_AUTO_RETRY_DELAY_SEC,
    MAX_RETRIES,
    RETRYABLE_STATUS_CODES,
)
from figma_flutter_agent.figma.models import FigmaImagesResponse


class ImagesEndpoint(FigmaEndpointBase):
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
        """Render image URLs for node ids in batches."""
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
                        transport_failure_message("GET", url, exc).replace(
                            "Figma API", "asset URL", 1
                        )
                    )
                    if attempt == MAX_RETRIES - 1:
                        raise last_error from exc
                    delay = float(2**attempt)
                    logger.warning(
                        "Asset download failed ({}) — retry in {:.0f}s ({}/{})",
                        format_transport_error(exc),
                        delay,
                        attempt + 2,
                        MAX_RETRIES,
                    )
                    await asyncio.sleep(delay)
                    continue

                if response.status_code == 200:
                    content: bytes = response.content
                    return content

                if response.status_code in RETRYABLE_STATUS_CODES and attempt < MAX_RETRIES - 1:
                    delay = retry_delay(response, attempt)
                    if response.status_code == 429 and delay > MAX_AUTO_RETRY_DELAY_SEC:
                        raise self._rate_limit_error(response, delay)
                    await asyncio.sleep(delay)
                    last_error = FigmaApiError(response.text, status_code=response.status_code)
                    continue

                raise FigmaApiError(response.text, status_code=response.status_code)

            if last_error:
                raise last_error
            raise FigmaApiError("Asset download failed after retries")
