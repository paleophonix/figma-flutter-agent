"""Asset lookup and export planning for render boundaries."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from loguru import logger

from figma_flutter_agent.schemas import AssetManifest, CleanDesignTreeNode

_ASSET_SCAN_FOLDERS = ("icons", "illustrations", "images")


def render_boundary_asset_path(node_id: str) -> str:
    """Relative Flutter asset path reserved for a render-boundary SVG export."""
    safe_id = node_id.replace(":", "_")
    return f"assets/illustrations/render_boundary_{safe_id}.svg"


def _register_asset_index_entry(
    entries: dict[str, list[tuple[tuple[int, str], str]]],
    safe_id: str,
    rel_path: str,
) -> None:
    rank = _vector_asset_discovery_rank(rel_path)
    entries[safe_id].append((rank, rel_path))


def build_asset_node_index(project_dir: Path) -> dict[str, str]:
    """Scan ``assets/`` once and map Figma node safe ids to best on-disk export path."""
    ranked: dict[str, list[tuple[tuple[int, str], str]]] = defaultdict(list)
    for folder in _ASSET_SCAN_FOLDERS:
        asset_dir = project_dir / "assets" / folder
        if not asset_dir.is_dir():
            continue
        for path in asset_dir.iterdir():
            if not path.is_file():
                continue
            suffix = path.suffix.lower()
            if suffix not in {".svg", ".png", ".webp", ".jpg", ".jpeg"}:
                continue
            rel = f"assets/{folder}/{path.name}".replace("\\", "/")
            stem = path.stem
            if stem.startswith("render_boundary_"):
                _register_asset_index_entry(
                    ranked,
                    stem.removeprefix("render_boundary_"),
                    rel,
                )
                continue
            parts = stem.split("_")
            for index in range(len(parts)):
                safe_id = "_".join(parts[index:])
                if safe_id:
                    _register_asset_index_entry(ranked, safe_id, rel)
    return {
        safe_id: min(paths, key=lambda item: item[0])[1]
        for safe_id, paths in ranked.items()
        if paths
    }


def lookup_asset_path_for_node(
    asset_index: dict[str, str],
    node_id: str,
) -> str | None:
    """Resolve one node id against a pre-built :func:`build_asset_node_index` map."""
    return asset_index.get(node_id.replace(":", "_"))


def discover_asset_path_for_node(
    project_dir: Path,
    node_id: str,
    *,
    asset_index: dict[str, str] | None = None,
) -> str | None:
    """Find an on-disk SVG/PNG export for a Figma node id (any filename suffix)."""
    if asset_index is not None:
        return lookup_asset_path_for_node(asset_index, node_id)
    suffix = node_id.replace(":", "_")
    best: tuple[tuple[int, str], str] | None = None
    for folder in _ASSET_SCAN_FOLDERS:
        asset_dir = project_dir / "assets" / folder
        if not asset_dir.is_dir():
            continue
        for pattern in (
            f"*_{suffix}.svg",
            f"*_{suffix}.png",
            f"render_boundary_{suffix}.svg",
        ):
            for match in asset_dir.glob(pattern):
                rel = f"assets/{folder}/{match.name}".replace("\\", "/")
                rank = _vector_asset_discovery_rank(rel)
                if best is None or rank < best[0]:
                    best = (rank, rel)
    return best[1] if best is not None else None


def _vector_asset_discovery_rank(asset_path: str) -> tuple[int, str]:
    """Prefer component chevron exports over raw parent-bound vector dumps."""
    lowered = asset_path.lower().replace("\\", "/")
    if "chevron-right" in lowered or "chevron_right" in lowered:
        return (0, lowered)
    if "/vector_" in lowered or lowered.rsplit("/", maxsplit=1)[-1].startswith("vector_"):
        return (2, lowered)
    return (1, lowered)


def _best_descendant_vector_asset(node: CleanDesignTreeNode) -> str | None:
    """Pick the most component-faithful vector export under a compact icon host."""
    from figma_flutter_agent.parser.interaction.shared import _descendant_nodes

    keys = [item.vector_asset_key for item in _descendant_nodes(node, 4) if item.vector_asset_key]
    if not keys:
        return None
    return min(keys, key=_vector_asset_discovery_rank)


def _composite_root_blocks_descendant_vector_promotion(
    node: CleanDesignTreeNode,
) -> bool:
    """Return True when hoisting a descendant SVG onto ``node`` would bypass composite emit."""
    from figma_flutter_agent.generator.layout.flex_policy.stack import (
        layout_fact_icon_badge_stack,
    )

    return layout_fact_icon_badge_stack(node)


def _product_photo_stack_geometry(
    node: CleanDesignTreeNode,
) -> tuple[float, float, float, float] | None:
    """Return geometric dimensions for a product-card photo stack."""
    from figma_flutter_agent.schemas import NodeType

    if node.type != NodeType.STACK or not node.children:
        return None
    photo = node.children[0]
    if photo.type != NodeType.CONTAINER or photo.children:
        return None
    width = node.sizing.width
    height = node.sizing.height
    photo_width = photo.sizing.width
    photo_height = photo.sizing.height
    if (
        width is None
        or height is None
        or photo_width is None
        or photo_height is None
        or float(width) <= 0
        or float(height) <= 0
        or float(photo_width) <= 0
        or float(photo_height) <= 0
    ):
        return None
    return (
        round(float(width), 1),
        round(float(height), 1),
        round(float(photo_width), 1),
        round(float(photo_height), 1),
    )


def _product_card_tile_identity(card: CleanDesignTreeNode) -> str:
    """Stable tile identity so geometrically equal product cards keep distinct rasters."""
    from figma_flutter_agent.parser.interaction import _descendant_nodes
    from figma_flutter_agent.schemas import NodeType

    if len(card.children) > 1:
        meta = card.children[1]
        for item in _descendant_nodes(meta, 6):
            if item.type != NodeType.TEXT:
                continue
            text = (item.text or "").strip()
            if text and text == text.upper() and len(text) <= 32:
                return f"cat:{text}"
        if meta.cluster_id:
            return f"cluster:{meta.cluster_id}"
    if card.children and card.children[0].cluster_id:
        return f"cluster:{card.children[0].cluster_id}"
    return ""


def _product_photo_stack_signature(
    node: CleanDesignTreeNode,
    *,
    parent_card: CleanDesignTreeNode | None,
) -> tuple[tuple[float, float, float, float], str] | None:
    """Return geometry plus tile identity so unlike catalog cards do not share rasters."""
    geometry = _product_photo_stack_geometry(node)
    if geometry is None:
        return None
    identity = _product_card_tile_identity(parent_card) if parent_card is not None else ""
    return geometry, identity


def resolve_structural_duplicate_image_assets(tree: CleanDesignTreeNode) -> None:
    """Copy ``imageAssetKey`` onto duplicate photo leaves that share the same stack shape."""
    from figma_flutter_agent.parser.tree_walk import walk_clean_tree_with_carry
    from figma_flutter_agent.schemas import NodeType

    signature_to_key: dict[tuple[tuple[float, float, float, float], str], str] = {}

    def carry_card(node: CleanDesignTreeNode, parent_card: CleanDesignTreeNode | None):
        return node if node.type == NodeType.CARD else parent_card

    def collect(node: CleanDesignTreeNode, parent_card: CleanDesignTreeNode | None) -> None:
        signature = _product_photo_stack_signature(node, parent_card=parent_card)
        if signature is not None:
            photo = node.children[0]
            if photo.image_asset_key:
                signature_to_key.setdefault(signature, photo.image_asset_key)

    def apply(node: CleanDesignTreeNode, parent_card: CleanDesignTreeNode | None) -> None:
        signature = _product_photo_stack_signature(node, parent_card=parent_card)
        if signature is not None:
            photo = node.children[0]
            if not photo.image_asset_key:
                shared = signature_to_key.get(signature)
                if shared is not None:
                    photo.image_asset_key = shared

    walk_clean_tree_with_carry(
        tree,
        collect,
        carry_card,
        None,
        phase="assets_structural_image_collect",
    )
    walk_clean_tree_with_carry(
        tree,
        apply,
        carry_card,
        None,
        phase="assets_structural_image_apply",
    )


def _discover_filter_raster_fallback_path(
    node: CleanDesignTreeNode,
    project_dir: Path,
    *,
    asset_index: dict[str, str] | None = None,
) -> str | None:
    """Locate a baked PNG fallback for a filtered SVG export."""
    if not node.vector_asset_key or not node.vector_asset_key.endswith(".svg"):
        return None
    sibling_png = node.vector_asset_key[:-4] + ".png"
    if (project_dir / sibling_png).is_file():
        return sibling_png.replace("\\", "/")
    stem = Path(node.vector_asset_key).stem
    for folder in ("images", "illustrations", "icons"):
        candidate = project_dir / "assets" / folder / f"{stem}.png"
        if candidate.is_file():
            return f"assets/{folder}/{candidate.name}".replace("\\", "/")
    for node_id in _vector_discovery_node_ids(node):
        discovered = discover_asset_path_for_node(
            project_dir,
            node_id,
            asset_index=asset_index,
        )
        if discovered is not None and discovered.endswith(".png"):
            return discovered.replace("\\", "/")
    return None


def resolve_missing_image_asset_keys(
    tree: CleanDesignTreeNode,
    project_dir: Path,
    *,
    asset_index: dict[str, str] | None = None,
) -> None:
    """Attach on-disk raster exports when the processed tree omitted ``imageAssetKey``."""
    from figma_flutter_agent.parser.interaction.enrichment import find_raster_photo_leaf
    from figma_flutter_agent.schemas import NodeType

    def _discover_image_key(
        node: CleanDesignTreeNode, *, parent: CleanDesignTreeNode | None
    ) -> str | None:
        for probe_id in _vector_discovery_node_ids(node):
            discovered = discover_asset_path_for_node(
                project_dir,
                probe_id,
                asset_index=asset_index,
            )
            if discovered is not None and discovered.endswith((".png", ".jpg", ".webp")):
                return discovered.replace("\\", "/")
        if parent is not None and parent.type == NodeType.STACK:
            discovered = discover_asset_path_for_node(
                project_dir,
                parent.id,
                asset_index=asset_index,
            )
            if discovered is not None and discovered.endswith((".png", ".jpg", ".webp")):
                return discovered.replace("\\", "/")
        return None

    def visit(node: CleanDesignTreeNode, parent: CleanDesignTreeNode | None) -> None:
        if not node.image_asset_key and node.type == NodeType.IMAGE:
            discovered = _discover_image_key(node, parent=parent)
            if discovered is not None:
                node.image_asset_key = discovered
        if (
            not node.image_asset_key
            and node.type == NodeType.VECTOR
            and node.sizing.width is not None
            and node.sizing.height is not None
            and float(node.sizing.width) >= 64.0
            and float(node.sizing.height) >= 48.0
        ):
            discovered = _discover_image_key(node, parent=parent)
            if discovered is not None:
                node.image_asset_key = discovered
        if (
            not node.image_asset_key
            and not node.children
            and node.type in {NodeType.CONTAINER, NodeType.IMAGE}
        ):
            discovered = discover_asset_path_for_node(
                project_dir,
                node.id,
                asset_index=asset_index,
            )
            if discovered is not None:
                node.image_asset_key = discovered.replace("\\", "/")

    from figma_flutter_agent.parser.tree_walk import walk_clean_tree_with_parent

    walk_clean_tree_with_parent(tree, visit)
    resolve_structural_duplicate_image_assets(tree)
    _resolve_filter_raster_fallback_keys(tree, project_dir, asset_index=asset_index)

    def propagate_avatar_parent_keys(node: CleanDesignTreeNode) -> None:
        photo = find_raster_photo_leaf(node)
        if photo is not None and not photo.image_asset_key and node.image_asset_key:
            photo.image_asset_key = node.image_asset_key

    from figma_flutter_agent.parser.tree_walk import walk_clean_tree

    walk_clean_tree(tree, propagate_avatar_parent_keys, phase="assets_avatar_propagate")


def _resolve_filter_raster_fallback_keys(
    tree: CleanDesignTreeNode,
    project_dir: Path,
    *,
    asset_index: dict[str, str] | None = None,
) -> None:
    """Bind PNG raster siblings when SVG exports need a baked raster tier."""
    from figma_flutter_agent.generator.layout.widgets.svg import SVG_PATH_RASTER_THRESHOLD

    def _node_prefers_raster_fallback(node: CleanDesignTreeNode) -> bool:
        if node.vector_svg_has_filter:
            return True
        path_count = node.vector_svg_path_count
        return path_count is not None and path_count > SVG_PATH_RASTER_THRESHOLD

    def visit(node: CleanDesignTreeNode) -> None:
        if (
            not node.image_asset_key
            and node.vector_asset_key
            and node.vector_asset_key.endswith(".svg")
            and _node_prefers_raster_fallback(node)
        ):
            fallback = _discover_filter_raster_fallback_path(
                node,
                project_dir,
                asset_index=asset_index,
            )
            if fallback is not None:
                node.image_asset_key = fallback

    from figma_flutter_agent.parser.tree_walk import walk_clean_tree

    walk_clean_tree(tree, visit)


def _vector_discovery_node_ids(node: CleanDesignTreeNode) -> list[str]:
    """Ordered Figma ids to probe for on-disk vector exports on ``node``."""
    seen: set[str] = set()
    ordered: list[str] = []

    def add(node_id: str | None) -> None:
        if node_id and node_id not in seen:
            seen.add(node_id)
            ordered.append(node_id)

    add(node.id)
    for flattened_id in node.flatten_figma_node_ids or ():
        add(flattened_id)

    from figma_flutter_agent.parser.tree_walk import walk_clean_tree

    for child in node.children:
        walk_clean_tree(child, lambda item, _add=add: _add(item.id), phase="assets_vector_discovery")
    return ordered


def _node_eligible_for_vector_asset_discovery(node: CleanDesignTreeNode) -> bool:
    """Return True when a clean-tree node may bind an on-disk SVG export."""
    from figma_flutter_agent.parser.interaction import layout_fact_compact_icon_action_button
    from figma_flutter_agent.schemas import NodeType

    if node.type in {
        NodeType.VECTOR,
        NodeType.STACK,
        NodeType.IMAGE,
        NodeType.ROW,
        NodeType.CONTAINER,
    }:
        return True
    return node.type == NodeType.BUTTON and layout_fact_compact_icon_action_button(node)


def resolve_discovered_vector_asset_keys(
    tree: CleanDesignTreeNode,
    project_dir: Path,
    *,
    asset_index: dict[str, str] | None = None,
) -> None:
    """Attach on-disk SVG exports when the clean tree omitted ``vectorAssetKey``.

    Offline dumps and deterministic re-emits often keep composite icon stacks
    (Google G, Facebook mark) without export metadata even though
    ``assets/icons/*_<node_id>.svg`` already exists in the Flutter project.
    Compact icon hosts (star rating, nav back) may export under a nested
    composite parent id while the cluster representative keeps only geometry.

    Args:
        tree: Normalized clean tree (mutated in place).
        project_dir: Flutter project root containing ``assets/``.
    """

    def visit(node: CleanDesignTreeNode) -> None:
        if node.vector_asset_key or not _node_eligible_for_vector_asset_discovery(node):
            return
        if _composite_root_blocks_descendant_vector_promotion(node):
            return
        candidates: list[str] = []
        for node_id in _vector_discovery_node_ids(node):
            discovered = discover_asset_path_for_node(
                project_dir,
                node_id,
                asset_index=asset_index,
            )
            if discovered is not None:
                candidates.append(discovered.replace("\\", "/"))
        if candidates:
            node.vector_asset_key = min(candidates, key=_vector_asset_discovery_rank)
            return
        from figma_flutter_agent.parser.tree_text import subtree_has_text_descendant

        if subtree_has_text_descendant(node):
            return
        promoted = _best_descendant_vector_asset(node)
        if promoted is not None:
            node.vector_asset_key = promoted

    from figma_flutter_agent.parser.tree_walk import walk_clean_tree

    walk_clean_tree(tree, visit, post_order=True)


def resolve_pruned_cluster_instance_assets(
    tree: CleanDesignTreeNode,
    project_dir: Path,
    manifest: AssetManifest | None = None,
    *,
    asset_index: dict[str, str] | None = None,
) -> None:
    """Attach per-instance vector exports onto pruned duplicate cluster nodes."""
    manifest_paths: dict[str, str] = {}
    if manifest is not None:
        for entry in manifest.entries:
            if entry.kind in {"icon", "illustration", "image"}:
                manifest_paths.setdefault(entry.node_id, entry.asset_path)

    def candidate_paths(node_id: str) -> list[str]:
        paths: list[str] = []
        manifest_path = manifest_paths.get(node_id)
        if manifest_path:
            paths.append(manifest_path)
        discovered = discover_asset_path_for_node(
            project_dir,
            node_id,
            asset_index=asset_index,
        )
        if discovered and discovered not in paths:
            paths.append(discovered)
        return paths

    def visit(node: CleanDesignTreeNode) -> None:
        if node.cluster_id and not node.children:
            resolved: str | None = None
            candidate_ids: list[str] = []
            for node_id in node.flatten_figma_node_ids or ():
                candidate_ids.append(node_id)
            candidate_ids.append(node.id)
            for node_id in candidate_ids:
                for candidate in candidate_paths(node_id):
                    if (project_dir / Path(candidate)).is_file():
                        resolved = candidate.replace("\\", "/")
                        break
                if resolved is not None:
                    break
            if resolved is not None:
                node.vector_asset_key = resolved

    from figma_flutter_agent.parser.tree_walk import walk_clean_tree

    walk_clean_tree(tree, visit)


def resolve_render_boundary_asset_keys(
    tree: CleanDesignTreeNode,
    project_dir: Path,
    manifest: AssetManifest | None = None,
    *,
    strict: bool = False,
) -> list[str]:
    """Map render-boundary nodes to existing exports; return ids still missing on disk."""
    manifest_paths: dict[str, str] = {}
    if manifest is not None:
        for entry in manifest.entries:
            manifest_paths.setdefault(entry.node_id, entry.asset_path)

    unresolved: list[str] = []

    def visit_boundary(node: CleanDesignTreeNode) -> None:
        if not node.render_boundary:
            return
        candidates: list[str] = []
        manifest_path = manifest_paths.get(node.id)
        if manifest_path:
            candidates.append(manifest_path)
        reserved = render_boundary_asset_path(node.id)
        if reserved not in candidates:
            candidates.append(reserved)
        discovered = discover_asset_path_for_node(project_dir, node.id)
        if discovered and discovered not in candidates:
            candidates.append(discovered)
        for candidate in candidates:
            if (project_dir / Path(candidate)).is_file():
                node.vector_asset_key = candidate.replace("\\", "/")
                break
        else:
            unresolved.append(node.id)
            if not strict:
                node.vector_asset_key = None
                node.image_asset_key = None

    from figma_flutter_agent.parser.tree_walk import walk_clean_tree

    walk_clean_tree(tree, visit_boundary, phase="assets_render_boundary_resolve")
    if unresolved:
        if strict:
            from figma_flutter_agent.errors import GenerationError

            raise GenerationError(
                "Render-boundary asset(s) missing on disk: " + ", ".join(sorted(unresolved))
            )
        logger.warning(
            "Render-boundary asset(s) missing on disk ({}); emit may use placeholder",
            ", ".join(sorted(unresolved)),
        )
    return unresolved


def collect_render_boundary_asset_plan(
    root: CleanDesignTreeNode,
) -> tuple[frozenset[str], frozenset[str]]:
    """Return boundary export ids and flattened descendant ids excluded from per-vector export."""
    export_ids: set[str] = set()
    exclude_ids: set[str] = set()

    def visit(node: CleanDesignTreeNode) -> None:
        if node.render_boundary:
            export_ids.add(node.id)
            for flattened_id in node.flatten_figma_node_ids or ():
                exclude_ids.add(flattened_id)

    from figma_flutter_agent.parser.tree_walk import walk_clean_tree

    walk_clean_tree(root, visit, phase="assets_render_boundary_plan")
    return frozenset(export_ids), frozenset(exclude_ids)
