"""Shared font resolution types."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ResolvedFontAsset:
    """One downloadable font file for a resolved face."""

    figma_family: str
    pubspec_family: str
    asset_name: str
    download_url: str
    weight: int
    style: str | None
    source: str
    local_path: Path | None = None
    is_analog: bool = False
