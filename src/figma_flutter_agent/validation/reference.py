"""Figma reference export and layout metric validation."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from loguru import logger

from figma_flutter_agent.debug.migrate import ensure_project_debug_layout
from figma_flutter_agent.debug.paths import (
    FIGMA_REFERENCE_REL,
    debug_path_display,
    figma_reference_metadata_path,
    figma_reference_png_path,
    legacy_figma_reference_dir,
    legacy_v2_figma_reference_png_path,
)
from figma_flutter_agent.figma.client import FigmaConnector

REFERENCE_DIR_NAME = FIGMA_REFERENCE_REL


@dataclass(frozen=True)
class FigmaReferenceExport:
    """Paths and metadata for an exported Figma reference screenshot."""

    image_path: Path
    metadata_path: Path
    image_hash: str
    width: float | None
    height: float | None


@dataclass(frozen=True)
class ReferencePngResolution:
    """Resolved Figma reference PNG bytes for LLM and/or visual QA."""

    png_bytes: bytes | None
    image_hash: str | None
    export: FigmaReferenceExport | None


def reference_png_path(project_dir: Path, feature_name: str) -> Path:
    """Return the on-disk path for a feature reference PNG."""
    return figma_reference_png_path(project_dir, feature_name)


def resolve_reference_png_path(project_dir: Path, feature_name: str) -> Path | None:
    """Return an existing Figma reference PNG path after layout migration."""
    ensure_project_debug_layout(project_dir)
    for path in (
        figma_reference_png_path(project_dir, feature_name),
        legacy_v2_figma_reference_png_path(project_dir, feature_name),
        legacy_figma_reference_dir(project_dir) / f"{feature_name}_figma.png",
    ):
        if path.is_file():
            return path
    return None


def load_cached_reference_png(project_dir: Path, feature_name: str) -> bytes | None:
    """Load a previously exported reference PNG when present."""
    path = resolve_reference_png_path(project_dir, feature_name)
    if path is None:
        return None
    return path.read_bytes()


def collect_layout_metric_warnings(
    figma_root: dict[str, Any],
    *,
    max_web_width: int,
) -> list[str]:
    """Compare Figma frame dimensions against responsive generation settings."""
    warnings: list[str] = []
    bounds = figma_root.get("absoluteBoundingBox")
    if not isinstance(bounds, dict):
        return warnings

    width = bounds.get("width")
    height = bounds.get("height")
    if isinstance(width, (int, float)) and width > max_web_width:
        warnings.append(
            f"Figma frame width ({width:g}px) exceeds configured maxWebWidth ({max_web_width}px)."
        )
    if (
        isinstance(width, (int, float))
        and isinstance(height, (int, float))
        and height > width * 2.5
    ):
        warnings.append(
            f"Figma frame aspect ratio is very tall ({width:g}x{height:g}); verify scroll/layout behavior."
        )
    return warnings


async def fetch_figma_reference_png_bytes(
    connector: FigmaConnector,
    *,
    file_key: str,
    node_id: str,
    scale: float = 2.0,
) -> bytes | None:
    """Download a Figma PNG export for a single frame node.

    Args:
        connector: Active Figma connector.
        file_key: Figma file key.
        node_id: Root frame node id.
        scale: PNG export scale for the Figma Images API.

    Returns:
        PNG bytes when the image download succeeds, otherwise ``None``.
    """
    fetch_result = await connector.fetch_image_urls(file_key, [node_id], fmt="png", scale=scale)
    image_url = fetch_result.urls.get(node_id)
    if not image_url:
        logger.warning("Figma reference fetch skipped: no image URL for node {}", node_id)
        return None
    return await connector.download_bytes(image_url)


def _write_reference_export(
    *,
    project_dir: Path,
    feature_name: str,
    file_key: str,
    node_id: str,
    scale: float,
    figma_root: dict[str, Any],
    image_bytes: bytes,
) -> FigmaReferenceExport:
    image_path = figma_reference_png_path(project_dir, feature_name)
    image_path.parent.mkdir(parents=True, exist_ok=True)
    image_path.write_bytes(image_bytes)

    bounds = figma_root.get("absoluteBoundingBox")
    width = bounds.get("width") if isinstance(bounds, dict) else None
    height = bounds.get("height") if isinstance(bounds, dict) else None
    metadata = {
        "fileKey": file_key,
        "nodeId": node_id,
        "featureName": feature_name,
        "scale": scale,
        "width": width,
        "height": height,
        "imagePath": debug_path_display(image_path, project_dir),
    }
    metadata_path = figma_reference_metadata_path(project_dir, feature_name)
    metadata_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")

    image_hash = hashlib.sha256(image_bytes).hexdigest()
    logger.info("Exported Figma reference screenshot to {}", image_path)
    return FigmaReferenceExport(
        image_path=image_path,
        metadata_path=metadata_path,
        image_hash=image_hash,
        width=float(width) if isinstance(width, (int, float)) else None,
        height=float(height) if isinstance(height, (int, float)) else None,
    )


async def export_figma_reference(
    connector: FigmaConnector,
    *,
    file_key: str,
    node_id: str,
    project_dir: Path,
    feature_name: str,
    figma_root: dict[str, Any],
    scale: float = 2.0,
) -> FigmaReferenceExport | None:
    """Download a Figma PNG reference screenshot for visual QA.

    Args:
        connector: Active Figma connector.
        file_key: Figma file key.
        node_id: Root frame node id.
        project_dir: Flutter project directory.
        feature_name: Generated feature folder name.
        figma_root: Parsed Figma root node used for layout metadata.
        scale: PNG export scale for the Figma Images API.

    Returns:
        Export metadata when the image download succeeds, otherwise ``None``.
    """
    image_bytes = await fetch_figma_reference_png_bytes(
        connector,
        file_key=file_key,
        node_id=node_id,
        scale=scale,
    )
    if image_bytes is None:
        return None
    return _write_reference_export(
        project_dir=project_dir,
        feature_name=feature_name,
        file_key=file_key,
        node_id=node_id,
        scale=scale,
        figma_root=figma_root,
        image_bytes=image_bytes,
    )


async def resolve_figma_reference_png(
    *,
    connector: FigmaConnector | None,
    file_key: str,
    node_id: str,
    project_dir: Path,
    feature_name: str,
    figma_root: dict[str, Any],
    scale: float,
    attach_to_llm: bool,
    save_to_disk: bool,
    from_dump: bool,
) -> ReferencePngResolution:
    """Resolve reference PNG bytes for LLM vision and optional on-disk export.

    Args:
        connector: Active Figma connector for live fetch; ``None`` in dump mode.
        file_key: Figma file key.
        node_id: Root frame node id.
        project_dir: Flutter project directory.
        feature_name: Generated feature folder name.
        figma_root: Parsed Figma root node used for layout metadata.
        scale: PNG export scale for the Figma Images API.
        attach_to_llm: When True, return PNG bytes for multimodal LLM input.
        save_to_disk: When True, persist PNG/JSON under ``.debug/reference/figma/``.
        from_dump: When True, load cached PNG instead of calling the Figma API.

    Returns:
        Resolved PNG bytes, optional content hash, and optional export metadata.
    """
    if not attach_to_llm and not save_to_disk:
        return ReferencePngResolution(png_bytes=None, image_hash=None, export=None)

    if from_dump:
        cached = load_cached_reference_png(project_dir, feature_name)
        if cached is None:
            return ReferencePngResolution(png_bytes=None, image_hash=None, export=None)
        image_hash = hashlib.sha256(cached).hexdigest()
        return ReferencePngResolution(
            png_bytes=cached if attach_to_llm else None, image_hash=image_hash, export=None
        )

    if connector is None:
        return ReferencePngResolution(png_bytes=None, image_hash=None, export=None)

    image_bytes = await fetch_figma_reference_png_bytes(
        connector,
        file_key=file_key,
        node_id=node_id,
        scale=scale,
    )
    if image_bytes is None:
        return ReferencePngResolution(png_bytes=None, image_hash=None, export=None)

    export = None
    if save_to_disk:
        export = _write_reference_export(
            project_dir=project_dir,
            feature_name=feature_name,
            file_key=file_key,
            node_id=node_id,
            scale=scale,
            figma_root=figma_root,
            image_bytes=image_bytes,
        )

    image_hash = (
        export.image_hash if export is not None else hashlib.sha256(image_bytes).hexdigest()
    )
    return ReferencePngResolution(
        png_bytes=image_bytes if attach_to_llm else None,
        image_hash=image_hash,
        export=export,
    )
