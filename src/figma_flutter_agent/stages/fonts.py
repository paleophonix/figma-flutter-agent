"""Font export stage."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from figma_flutter_agent.config import FontsConfig
from figma_flutter_agent.fonts.apply import apply_font_manifest
from figma_flutter_agent.fonts.bundle import bundle_fonts_for_tree
from figma_flutter_agent.schemas import CleanDesignTreeNode, FontManifest


@dataclass
class FontExportRequest:
    """Inputs for bundled font export."""

    project_dir: Path
    clean_tree: CleanDesignTreeNode
    fonts: FontsConfig
    destination_trees: dict[str, CleanDesignTreeNode] | None = None


def export_fonts(request: FontExportRequest) -> FontManifest:
    """Bundle fonts required by the clean tree into the Flutter project."""
    manifest = bundle_fonts_for_tree(
        request.clean_tree,
        request.project_dir,
        enabled=request.fonts.enabled,
        cache_enabled=request.fonts.cache_enabled,
    )
    apply_font_manifest(request.clean_tree, manifest)
    if request.destination_trees:
        for tree in request.destination_trees.values():
            apply_font_manifest(tree, manifest)
    return manifest
