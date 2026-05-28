"""Sync project ``assets/fonts/`` after Figma fetch/import."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from loguru import logger

from figma_flutter_agent.config import FontsConfig
from figma_flutter_agent.fonts.bundle import bundle_font_faces
from figma_flutter_agent.fonts.collector import collect_font_faces_from_figma_document
from figma_flutter_agent.schemas import CleanDesignTreeNode, FontManifest


def _log_font_warnings(manifest: FontManifest, *, stage: str) -> None:
    for message in manifest.warnings:
        logger.bind(stage=stage).warning("{}", message)


def sync_fonts_from_figma_document(
    project_dir: Path,
    document: dict[str, Any],
    fonts: FontsConfig,
) -> FontManifest:
    """Ensure ``assets/fonts/`` contains design fonts after a frame dump/import.

    Args:
        project_dir: Flutter project root.
        document: Raw Figma frame document JSON.
        fonts: Agent font settings.

    Returns:
        Font manifest from resolution (may be empty when fonts are disabled).
    """
    if not fonts.enabled:
        return FontManifest()

    faces = collect_font_faces_from_figma_document(document)
    if not faces:
        return FontManifest()

    manifest = bundle_font_faces(
        faces,
        project_dir,
        download_fonts=fonts.download_fonts,
        cache_enabled=fonts.cache_enabled,
        phase="fetch",
    )
    _log_font_warnings(manifest, stage="fonts-fetch")
    return manifest


def sync_fonts_from_clean_tree(
    project_dir: Path,
    tree: CleanDesignTreeNode,
    fonts: FontsConfig,
) -> FontManifest:
    """Sync fonts from a parsed clean tree (fetch-time or offline import)."""
    from figma_flutter_agent.fonts.bundle import bundle_fonts_for_tree

    if not fonts.enabled:
        return FontManifest()

    manifest = bundle_fonts_for_tree(
        tree,
        project_dir,
        enabled=True,
        download_fonts=fonts.download_fonts,
        cache_enabled=fonts.cache_enabled,
        phase="fetch",
    )
    _log_font_warnings(manifest, stage="fonts-fetch")
    return manifest
