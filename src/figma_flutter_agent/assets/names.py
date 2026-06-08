"""Asset filename helpers."""

from __future__ import annotations

import re

SAFE_NAME = re.compile(r"[^a-zA-Z0-9_-]+")


def safe_filename(name: str) -> str:
    cleaned = SAFE_NAME.sub("_", name.strip().lower()).strip("_")
    return cleaned or "asset"


def asset_filename(name: str, node_id: str, extension: str) -> str:
    """Build a collision-safe asset filename using the Figma node id."""
    node_suffix = node_id.replace(":", "_")
    return f"{safe_filename(name)}_{node_suffix}.{extension}"
