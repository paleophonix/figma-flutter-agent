"""Guardrails for screen-frame assets that must never be used as UI layers."""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path

from loguru import logger

from figma_flutter_agent.schemas import AssetManifest, CleanDesignTreeNode

_NODE_ID_SUFFIX_RE = re.compile(r"_(?P<suffix>(?:I?\d+_\d+)(?:;(?:I?\d+)?\d+_\d+)*)$")
_SVG_ASSET_PATH_RE = re.compile(
    r"SvgPicture\.asset\(\s*['\"](?P<path>assets/[^'\"]+)['\"]",
)
_IMAGE_ASSET_PATH_RE = re.compile(
    r"Image\.asset\(\s*['\"](?P<path>assets/[^'\"]+)['\"]",
)


def build_screen_frame_exclude_ids(
    primary_node_id: str,
    destination_node_ids: Iterable[str] | None = None,
) -> frozenset[str]:
    """Return Figma node ids that represent whole screen frames, not exportable assets."""
    excluded = {primary_node_id}
    if destination_node_ids is not None:
        excluded.update(destination_node_ids)
    return frozenset(excluded)


def node_id_from_asset_stem(stem: str) -> str | None:
    """Parse a Figma node id suffix from an asset filename stem."""
    match = _NODE_ID_SUFFIX_RE.search(stem)
    if match is None:
        return None
    return match.group("suffix").replace("_", ":")


def filter_manifest(manifest: AssetManifest, exclude_node_ids: frozenset[str]) -> AssetManifest:
    """Drop manifest entries tied to excluded screen-frame node ids."""
    if not exclude_node_ids:
        return manifest
    entries = [entry for entry in manifest.entries if entry.node_id not in exclude_node_ids]
    return AssetManifest(entries=entries)


def strip_screen_frame_assets_from_tree(
    tree: CleanDesignTreeNode,
    exclude_node_ids: frozenset[str],
) -> None:
    """Clear asset keys on excluded screen-frame nodes before LLM or layout codegen."""
    if not exclude_node_ids:
        return

    def walk(node: CleanDesignTreeNode) -> None:
        if node.id in exclude_node_ids:
            node.vector_asset_key = None
            node.image_asset_key = None
            node.vector_svg_has_filter = False
        for child in node.children:
            walk(child)

    walk(tree)


def collect_blocked_asset_paths(
    project_dir: Path,
    exclude_node_ids: frozenset[str],
) -> frozenset[str]:
    """Collect on-disk asset paths that belong to excluded screen-frame node ids."""
    if not exclude_node_ids:
        return frozenset()

    blocked: set[str] = set()
    for directory in ("icons", "images", "illustrations"):
        asset_dir = project_dir / "assets" / directory
        if not asset_dir.is_dir():
            continue
        for path in asset_dir.iterdir():
            if not path.is_file():
                continue
            node_id = node_id_from_asset_stem(path.stem)
            if node_id is None or node_id not in exclude_node_ids:
                continue
            blocked.add(f"assets/{directory}/{path.name}".replace("\\", "/"))
    return frozenset(blocked)


def prune_screen_frame_assets(
    project_dir: Path,
    exclude_node_ids: frozenset[str],
) -> list[str]:
    """Delete stale screen-frame assets from the Flutter project asset folders."""
    if not exclude_node_ids:
        return []

    removed: list[str] = []
    for directory in ("icons", "images", "illustrations"):
        asset_dir = project_dir / "assets" / directory
        if not asset_dir.is_dir():
            continue
        for path in sorted(asset_dir.iterdir()):
            if not path.is_file():
                continue
            node_id = node_id_from_asset_stem(path.stem)
            if node_id is None or node_id not in exclude_node_ids:
                continue
            path.unlink(missing_ok=True)
            removed.append(path.as_posix())
            logger.info("Removed stale screen-frame asset {}", path.as_posix())
    return removed


def manifest_entries_for_prompt(manifest: AssetManifest) -> list[dict[str, str]]:
    """Serialize manifest entries for LLM payloads."""
    return [entry.model_dump() for entry in manifest.entries]


def sanitize_dart_blocked_assets(source: str, blocked_paths: frozenset[str]) -> str:
    """Remove Dart widget blocks that reference blocked screen-frame asset paths."""
    if not blocked_paths:
        return source

    updated = source
    for asset_path in sorted(blocked_paths, key=len, reverse=True):
        escaped = re.escape(asset_path)
        updated = re.sub(
            rf"^\s*Positioned(?:\.fill)?\(\s*\n"
            rf"(?:.*\n)*?"
            rf"\s*child:\s*SvgPicture\.asset\(\s*\n?"
            rf"\s*['\"]{escaped}['\"][\s\S]*?"
            rf"\s*\),\s*\n?"
            rf"\s*\),\s*\n?",
            "",
            updated,
            flags=re.MULTILINE,
        )
        updated = re.sub(
            rf"^\s*Positioned(?:\.fill)?\(\s*\n"
            rf"(?:.*\n)*?"
            rf"\s*child:\s*Image\.asset\(\s*\n?"
            rf"\s*['\"]{escaped}['\"][\s\S]*?"
            rf"\s*\),\s*\n?"
            rf"\s*\),\s*\n?",
            "",
            updated,
            flags=re.MULTILINE,
        )
        updated = re.sub(
            rf"^\s*SvgPicture\.asset\(\s*['\"]{escaped}['\"][^\n]*\n",
            "",
            updated,
            flags=re.MULTILINE,
        )
        updated = re.sub(
            rf"^\s*Image\.asset\(\s*['\"]{escaped}['\"][^\n]*\n",
            "",
            updated,
            flags=re.MULTILINE,
        )
    return updated


def extract_asset_paths_from_dart(source: str) -> frozenset[str]:
    """Collect SvgPicture/Image asset paths referenced in generated Dart."""
    paths = {match.group("path") for match in _SVG_ASSET_PATH_RE.finditer(source)}
    paths.update(match.group("path") for match in _IMAGE_ASSET_PATH_RE.finditer(source))
    return frozenset(paths)
