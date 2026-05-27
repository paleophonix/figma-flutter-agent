"""Apply font manifest metadata to a clean design tree."""

from __future__ import annotations

from figma_flutter_agent.fonts.collector import _walk
from figma_flutter_agent.fonts.sources import normalize_figma_family
from figma_flutter_agent.schemas import CleanDesignTreeNode, FontManifest, NodeType


def apply_font_manifest(tree: CleanDesignTreeNode, manifest: FontManifest) -> None:
    """Normalize ``TEXT`` node families to bundled pubspec family names."""
    if not manifest.bundled_family_names:
        return
    bundled = set(manifest.bundled_family_names)
    for node in _walk(tree):
        if node.type != NodeType.TEXT or not node.style.font_family:
            continue
        raw_family = node.style.font_family
        aliased = manifest.family_aliases.get(raw_family)
        if aliased is not None and aliased in bundled:
            node.style.font_family = aliased
            continue
        normalized = normalize_figma_family(raw_family)
        if normalized in bundled:
            node.style.font_family = normalized
