"""Figma image export models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ImageUrlFetchResult:
    """Outcome of batched Figma Images API requests."""

    urls: dict[str, str]
    failed_node_ids: tuple[str, ...]
    rate_limited: bool
