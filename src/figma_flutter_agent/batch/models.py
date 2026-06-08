"""Batch manifest data models."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ScreenEntry:
    """One screen in a batch manifest."""

    feature: str
    node_id: str
    dump: Path | None = None
    figma_url: str | None = None


@dataclass(frozen=True)
class BatchManifest:
    """YAML manifest describing multiple Figma screens."""

    file_key: str
    project_dir: Path
    screens: tuple[ScreenEntry, ...]
    figma_file_url: str | None = None
