"""Reuse exported assets already present in a Flutter project."""

from __future__ import annotations

import json
import re
from pathlib import Path

from loguru import logger

from figma_flutter_agent.assets.optimize import svg_has_unsupported_filter, svg_path_element_count
from figma_flutter_agent.assets.screen_frame import node_id_from_asset_stem
from figma_flutter_agent.generator.ir.tree import index_clean_tree
from figma_flutter_agent.schemas import (
    AssetManifest,
    AssetManifestEntry,
    CleanDesignTreeNode,
    NodeType,
)
from figma_flutter_agent.validation.geometry_metrics import build_parent_map

_BINDINGS_FILENAME = ".figma-bindings.json"
_RASTER_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp")
_GENERIC_NODE_NAMES = frozenset(
    {
        "container",
        "button",
        "overlay",
        "overlay+overlayblur",
        "background",
        "image",
        "fallback-image.svg fill",
    }
)
_BINDING_LABEL_ANCESTOR_LIMIT = 3
_BINDING_SUBTREE_TEXT_MAX_DEPTH = 2
_VARIANT_VALUE_BINDING_ALIASES: dict[str, list[str]] = {
    "delivered": ["meal"],
}
_PRODUCT_ROW_MEDIA_CHILD_TYPES = frozenset({NodeType.IMAGE, NodeType.STACK, NodeType.CONTAINER})
_CYRILLIC_TRANSLIT = str.maketrans(
    {
        "а": "a",
        "б": "b",
        "в": "v",
        "г": "g",
        "д": "d",
        "е": "e",
        "ё": "e",
        "ж": "zh",
        "з": "z",
        "и": "i",
        "й": "y",
        "к": "k",
        "л": "l",
        "м": "m",
        "н": "n",
        "о": "o",
        "п": "p",
        "р": "r",
        "с": "s",
        "т": "t",
        "у": "u",
        "ф": "f",
        "х": "h",
        "ц": "ts",
        "ч": "ch",
        "ш": "sh",
        "щ": "sch",
        "ъ": "",
        "ы": "y",
        "ь": "",
        "э": "e",
        "ю": "yu",
        "я": "ya",
    }
)


def load_project_asset_bindings(project_dir: Path) -> dict[str, str]:
    """Load optional filename-to-node-id bindings from ``assets/images/.figma-bindings.json``."""
    bindings_path = project_dir / "assets" / "images" / _BINDINGS_FILENAME
    if not bindings_path.is_file():
        return {}
    try:
        payload = json.loads(bindings_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        logger.warning("Ignoring invalid {}: {}", bindings_path.as_posix(), exc)
        return {}
    raw = payload.get("bindings", payload)
    if not isinstance(raw, dict):
        return {}
    bindings: dict[str, str] = {}
    for filename, node_id in raw.items():
        if not isinstance(filename, str) or not isinstance(node_id, str):
            continue
        normalized_name = filename.replace("\\", "/").split("/")[-1].strip()
        normalized_id = node_id.strip()
        if normalized_name and normalized_id:
            bindings[normalized_name] = normalized_id
    return bindings


def _normalize_binding_text(value: str) -> str:
    lowered = value.strip().lower().replace("\n", " ")
    transliterated = lowered.translate(_CYRILLIC_TRANSLIT)
    return re.sub(r"[^a-z0-9]+", " ", transliterated).strip()


def _is_raster_binding_target(node: CleanDesignTreeNode) -> bool:
    if node.type == NodeType.IMAGE:
        return True
    if node.render_boundary and node.flatten_figma_node_ids:
        width = node.sizing.width or 0.0
        height = node.sizing.height or 0.0
        if width >= 64.0 and height >= 64.0:
            return True
    if node.type == NodeType.STACK and node.component_ref:
        width = node.sizing.width or 0.0
        height = node.sizing.height or 0.0
        if 20.0 <= width <= 48.0 and 20.0 <= height <= 48.0:
            return True
    if node.type != NodeType.CONTAINER or node.children:
        return False
    width = node.sizing.width or 0.0
    height = node.sizing.height or 0.0
    return width >= 64.0 and height >= 64.0


def _subtree_text_labels(node: CleanDesignTreeNode, *, max_depth: int) -> list[str]:
    labels: list[str] = []

    def walk(current: CleanDesignTreeNode, depth: int) -> None:
        if depth > max_depth:
            return
        if current.type == NodeType.TEXT:
            labels.append(current.text or current.name or "")
        for child in current.children:
            walk(child, depth + 1)

    walk(node, 0)
    return labels


def _component_name_path_labels(name: str | None) -> list[str]:
    if not name:
        return []
    return [part.strip() for part in name.replace("\\", "/").split("/") if part.strip()]


def _nearest_product_row_scope(
    node_id: str,
    *,
    tree_by_id: dict[str, CleanDesignTreeNode],
    parent_by_id: dict[str, str],
) -> CleanDesignTreeNode | None:
    """Return the closest product image+title row ancestor for label scoping."""
    current = node_id
    for _ in range(12):
        parent_id = parent_by_id.get(current)
        if parent_id is None:
            break
        parent = tree_by_id.get(parent_id)
        if parent is None:
            break
        if parent.type == NodeType.ROW:
            has_media = any(
                child.type in _PRODUCT_ROW_MEDIA_CHILD_TYPES
                and (child.type == NodeType.IMAGE or _is_raster_binding_target(child))
                for child in parent.children
            )
            has_text = any(
                child.type == NodeType.TEXT
                or any(
                    grandchild.type == NodeType.TEXT and (grandchild.text or "").strip()
                    for grandchild in child.children
                )
                for child in parent.children
            )
            if has_media and has_text:
                return parent
        current = parent_id
    return None


def _collect_binding_labels(
    node_id: str,
    *,
    tree_by_id: dict[str, CleanDesignTreeNode],
    parent_by_id: dict[str, str],
) -> list[str]:
    labels: list[str] = []
    seen: set[str] = set()

    def add_label(value: str | None) -> None:
        if not value:
            return
        normalized = _normalize_binding_text(value)
        if normalized and normalized not in seen:
            seen.add(normalized)
            labels.append(normalized)

    target = tree_by_id.get(node_id)
    if target is not None:
        if target.name and target.name.lower() not in _GENERIC_NODE_NAMES:
            add_label(target.name)
        add_label(target.accessibility_label)
        if target.variant is not None:
            add_label(target.variant.component_name)
            for part in _component_name_path_labels(target.variant.component_name):
                add_label(part)
            for value in target.variant.variant_properties.values():
                add_label(str(value))
                alias_key = _normalize_binding_text(str(value))
                for alias in _VARIANT_VALUE_BINDING_ALIASES.get(alias_key, []):
                    add_label(alias)

    scope = _nearest_product_row_scope(
        node_id,
        tree_by_id=tree_by_id,
        parent_by_id=parent_by_id,
    )
    if scope is not None:
        for text_label in _subtree_text_labels(scope, max_depth=_BINDING_SUBTREE_TEXT_MAX_DEPTH):
            add_label(text_label)
    current = node_id
    for _ in range(_BINDING_LABEL_ANCESTOR_LIMIT):
        parent_id = parent_by_id.get(current)
        if parent_id is None:
            break
        parent = tree_by_id.get(parent_id)
        if parent is None:
            break
        if parent.name and parent.name.lower() not in _GENERIC_NODE_NAMES:
            add_label(parent.name)
        for part in _component_name_path_labels(parent.name):
            add_label(part)
        if parent.variant is not None:
            add_label(parent.variant.component_name)
            for part in _component_name_path_labels(parent.variant.component_name):
                add_label(part)
            for value in parent.variant.variant_properties.values():
                add_label(str(value))
                alias_key = _normalize_binding_text(str(value))
                for alias in _VARIANT_VALUE_BINDING_ALIASES.get(alias_key, []):
                    add_label(alias)
        for child in parent.children:
            if child.type == NodeType.TEXT:
                add_label(child.text or child.name)
        current = parent_id
    return labels


def _stem_matches_labels(stem: str, labels: list[str]) -> bool:
    token = _normalize_binding_text(stem.replace("_", " "))
    if not token:
        return False
    stem_words = set(token.split())
    for label in labels:
        if token in label or label in token:
            return True
        label_words = set(label.split())
        if stem_words & label_words:
            return True
        words = label.split()
        if words and (words[0].startswith(token) or token.startswith(words[0])):
            return True
    return False


def _word_overlap_score(stem: str, labels: list[str]) -> int:
    stem_words = set(_normalize_binding_text(stem.replace("_", " ")).split())
    score = 0
    for label in labels:
        score += len(stem_words & set(label.split()))
    return score


def _orphan_raster_pairing(
    project_dir: Path,
    *,
    clean_tree: CleanDesignTreeNode,
    exclude_node_ids: frozenset[str],
    bound_node_ids: set[str],
    assigned_nodes: set[str],
) -> list[AssetManifestEntry]:
    """Assign remaining human-named rasters to unbound targets with best label overlap."""
    images_dir = project_dir / "assets" / "images"
    if not images_dir.is_dir():
        return []

    tree_by_id = index_clean_tree(clean_tree)
    parent_by_id = build_parent_map(clean_tree)
    orphan_files = [
        path
        for path in sorted(images_dir.iterdir())
        if path.suffix.lower() in _RASTER_SUFFIXES and node_id_from_asset_stem(path.stem) is None
    ]
    unbound_targets = [
        node_id
        for node_id, node in tree_by_id.items()
        if node_id not in exclude_node_ids
        and node_id not in bound_node_ids
        and node_id not in assigned_nodes
        and _is_raster_binding_target(node)
    ]
    if not orphan_files or not unbound_targets:
        return []

    entries: list[AssetManifestEntry] = []
    used_files: set[Path] = set()
    for node_id in sorted(unbound_targets):
        labels = _collect_binding_labels(
            node_id,
            tree_by_id=tree_by_id,
            parent_by_id=parent_by_id,
        )
        best_path: Path | None = None
        best_score = 0
        for path in orphan_files:
            if path in used_files:
                continue
            score = _word_overlap_score(path.stem, labels)
            if score > best_score:
                best_score = score
                best_path = path
        if best_path is None or best_score <= 0:
            continue
        used_files.add(best_path)
        assigned_nodes.add(node_id)
        entries.append(
            AssetManifestEntry(
                node_id=node_id,
                asset_path=f"assets/images/{best_path.name}",
                kind="image",
            )
        )
    return entries


def _semantic_raster_bindings(
    project_dir: Path,
    *,
    clean_tree: CleanDesignTreeNode,
    exclude_node_ids: frozenset[str],
    bound_node_ids: set[str],
) -> list[AssetManifestEntry]:
    images_dir = project_dir / "assets" / "images"
    if not images_dir.is_dir():
        return []

    tree_by_id = index_clean_tree(clean_tree)
    parent_by_id = build_parent_map(clean_tree)
    candidates: dict[str, list[str]] = {}
    for node_id, node in tree_by_id.items():
        if node_id in exclude_node_ids or node_id in bound_node_ids:
            continue
        if not _is_raster_binding_target(node):
            continue
        labels = _collect_binding_labels(
            node_id,
            tree_by_id=tree_by_id,
            parent_by_id=parent_by_id,
        )
        if labels:
            candidates[node_id] = labels

    entries: list[AssetManifestEntry] = []
    assigned_nodes: set[str] = set()
    for path in sorted(images_dir.iterdir()):
        if path.suffix.lower() not in _RASTER_SUFFIXES:
            continue
        if node_id_from_asset_stem(path.stem) is not None:
            continue
        token = _normalize_binding_text(path.stem.replace("_", " "))
        if not token:
            continue
        for node_id, labels in candidates.items():
            if node_id in assigned_nodes:
                continue
            if _stem_matches_labels(path.stem, labels):
                entries.append(
                    AssetManifestEntry(
                        node_id=node_id,
                        asset_path=f"assets/images/{path.name}",
                        kind="image",
                    )
                )
                assigned_nodes.add(node_id)
                break
    entries.extend(
        _orphan_raster_pairing(
            project_dir,
            clean_tree=clean_tree,
            exclude_node_ids=exclude_node_ids,
            bound_node_ids=bound_node_ids,
            assigned_nodes=assigned_nodes,
        )
    )
    return entries


def local_asset_manifest_from_project(
    project_dir: Path,
    *,
    exclude_node_ids: frozenset[str] | None = None,
    clean_tree: CleanDesignTreeNode | None = None,
) -> AssetManifest:
    """Build an asset manifest from on-disk project assets.

    Resolution order for raster images:
    1. Filename suffix ``*_610_833`` / ``610_833`` (Figma node id stem)
    2. Optional ``assets/images/.figma-bindings.json`` filename map
    3. Semantic match against nearby product/card labels when ``clean_tree`` is set
    """
    excludes = exclude_node_ids or frozenset()
    entries: list[AssetManifestEntry] = []
    bound_node_ids: set[str] = set()
    explicit_bindings = load_project_asset_bindings(project_dir)

    for svg_dir, kind in (("icons", "icon"), ("illustrations", "illustration")):
        asset_dir = project_dir / "assets" / svg_dir
        if not asset_dir.is_dir():
            continue
        for path in asset_dir.glob("*.svg"):
            node_id = node_id_from_asset_stem(path.stem)
            if node_id is None or node_id in excludes:
                continue
            svg_text = path.read_text(encoding="utf-8")
            entries.append(
                AssetManifestEntry(
                    node_id=node_id,
                    asset_path=f"assets/{svg_dir}/{path.name}",
                    kind=kind,
                    svg_has_filter=svg_has_unsupported_filter(svg_text),
                    svg_path_count=svg_path_element_count(svg_text),
                )
            )
            bound_node_ids.add(node_id)

    for directory, kind in (("images", "image"), ("illustrations", "illustration")):
        asset_dir = project_dir / "assets" / directory
        if not asset_dir.is_dir():
            continue
        for path in asset_dir.iterdir():
            if path.suffix.lower() not in _RASTER_SUFFIXES:
                continue
            node_id = node_id_from_asset_stem(path.stem)
            if node_id is None:
                node_id = explicit_bindings.get(path.name)
            if node_id is None or node_id in excludes:
                continue
            if node_id in bound_node_ids:
                svg_entry = next(
                    (
                        entry
                        for entry in entries
                        if entry.node_id == node_id and entry.kind != "image"
                    ),
                    None,
                )
                if not (svg_entry is not None and svg_entry.svg_has_filter):
                    continue
            entries.append(
                AssetManifestEntry(
                    node_id=node_id,
                    asset_path=f"assets/{directory}/{path.name}",
                    kind=kind,
                )
            )
            bound_node_ids.add(node_id)

    if clean_tree is not None:
        entries.extend(
            _semantic_raster_bindings(
                project_dir,
                clean_tree=clean_tree,
                exclude_node_ids=excludes,
                bound_node_ids=bound_node_ids,
            )
        )

    return AssetManifest(entries=entries)
