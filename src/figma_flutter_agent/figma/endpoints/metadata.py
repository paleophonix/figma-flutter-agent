"""Figma file metadata endpoint methods."""

from __future__ import annotations

from typing import Any

import httpx
from loguru import logger

from figma_flutter_agent.figma.models import (
    FigmaComponentSetsResponse,
    FigmaComponentsResponse,
    FigmaFileResponse,
    FigmaStylesResponse,
)


class MetadataEndpoint:
    async def fetch_file(self, file_key: str) -> FigmaFileResponse:
        """Fetch the full Figma file document (Tier 1)."""
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
