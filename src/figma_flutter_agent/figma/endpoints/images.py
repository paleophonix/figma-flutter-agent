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
    IMAGE_URL_NULL_RETRIES,
    IMAGE_URL_RETRY_DELAY_SEC,
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
        null_url_failed: list[str] = []
        rate_limit_failed: list[str] = []
        rate_limited = False

        async def _fetch_batch(batch: list[str]) -> list[str]:
            nonlocal rate_limited
            try:
                response = await self._request(
                    "GET",
                    f"/v1/images/{file_key}",
                    params={"ids": ",".join(batch), "format": fmt, "scale": scale},
                )
            except FigmaApiError as exc:
                if continue_on_rate_limit and exc.status_code == 429:
                    rate_limit_failed.extend(batch)
                    rate_limited = True
                    logger.warning(
                        "Figma images API rate limit (429); skipping {} node(s) and continuing",
                        len(batch),
                    )
                    await asyncio.sleep(max(inter_batch_delay_sec, 5.0))
                    return []
                raise
            payload = FigmaImagesResponse.model_validate(response.json())
            batch_failed: list[str] = []
            for node_id, image_url in payload.images.items():
                if node_id not in batch:
                    continue
                if image_url:
                    urls[node_id] = image_url
                else:
                    batch_failed.append(node_id)
            return batch_failed

        async def _fetch_all(pending_ids: list[str]) -> list[str]:
            unresolved: list[str] = []
            for index in range(0, len(pending_ids), BATCH_SIZE):
                if index > 0 and inter_batch_delay_sec > 0:
                    await asyncio.sleep(inter_batch_delay_sec)
                batch = pending_ids[index : index + BATCH_SIZE]
                unresolved.extend(await _fetch_batch(batch))
            return unresolved

        null_url_failed = await _fetch_all(node_ids)

        for attempt in range(IMAGE_URL_NULL_RETRIES):
            retry_ids = [node_id for node_id in null_url_failed if node_id not in urls]
            if not retry_ids:
                break
            delay = IMAGE_URL_RETRY_DELAY_SEC * (attempt + 1)
            logger.info(
                "Retrying {} Figma image URL(s) after {:.0f}s (attempt {}/{})",
                len(retry_ids),
                delay,
                attempt + 1,
                IMAGE_URL_NULL_RETRIES,
            )
            await asyncio.sleep(delay)
            null_url_failed = [
                node_id
                for node_id in dict.fromkeys(await _fetch_all(retry_ids))
                if node_id not in urls
            ]

        failed = rate_limit_failed + null_url_failed
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
