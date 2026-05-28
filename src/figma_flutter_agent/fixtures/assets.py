"""Offline fixture asset stubs for golden capture."""

from __future__ import annotations

import shutil
from pathlib import Path

from figma_flutter_agent.fixtures.screens_manifest import fixtures_root
from figma_flutter_agent.schemas import CleanDesignTreeNode

_PLACEHOLDER_SVG = fixtures_root() / "flutter_skeleton" / "assets" / "icons" / "placeholder.svg"


def iter_vector_asset_keys(root: CleanDesignTreeNode) -> set[str]:
    """Collect ``vectorAssetKey`` paths from a clean design tree."""
    keys: set[str] = set()

    def walk(node: CleanDesignTreeNode) -> None:
        if node.vector_asset_key:
            keys.add(node.vector_asset_key.replace("\\", "/"))
        for child in node.children:
            walk(child)

    walk(root)
    return keys


def sync_fixture_vector_assets(project_dir: Path, root: CleanDesignTreeNode) -> list[str]:
    """Copy the skeleton placeholder SVG for every referenced vector asset.

    Args:
        project_dir: Flutter project root used for golden capture.
        root: Layout fixture tree.

    Returns:
        Relative asset paths written under ``project_dir``.
    """
    if not _PLACEHOLDER_SVG.is_file():
        return []
    written: list[str] = []
    for asset_key in sorted(iter_vector_asset_keys(root)):
        if not asset_key.endswith(".svg"):
            continue
        destination = project_dir / asset_key.replace("/", "\\")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(_PLACEHOLDER_SVG, destination)
        written.append(asset_key)
    return written
