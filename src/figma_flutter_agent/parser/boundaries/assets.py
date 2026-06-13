"""Asset lookup and export planning for render boundaries."""

from __future__ import annotations

from pathlib import Path

from loguru import logger

from figma_flutter_agent.schemas import AssetManifest, CleanDesignTreeNode


def render_boundary_asset_path(node_id: str) -> str:
    """Relative Flutter asset path reserved for a render-boundary SVG export."""
    safe_id = node_id.replace(":", "_")
    return f"assets/illustrations/render_boundary_{safe_id}.svg"


def discover_asset_path_for_node(project_dir: Path, node_id: str) -> str | None:
    """Find an on-disk SVG/PNG export for a Figma node id (any filename suffix)."""
    suffix = node_id.replace(":", "_")
    for folder in ("icons", "illustrations", "images"):
        asset_dir = project_dir / "assets" / folder
        if not asset_dir.is_dir():
            continue
        for pattern in (
            f"*_{suffix}.svg",
            f"*_{suffix}.png",
            f"render_boundary_{suffix}.svg",
        ):
            matches = sorted(asset_dir.glob(pattern))
            if matches:
                return f"assets/{folder}/{matches[0].name}"
    return None


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
    from figma_flutter_agent.schemas import NodeType

    signature_to_key: dict[tuple[tuple[float, float, float, float], str], str] = {}

    def collect(node: CleanDesignTreeNode, parent_card: CleanDesignTreeNode | None) -> None:
        parent_card = node if node.type == NodeType.CARD else parent_card
        signature = _product_photo_stack_signature(node, parent_card=parent_card)
        if signature is not None:
            photo = node.children[0]
            if photo.image_asset_key:
                signature_to_key.setdefault(signature, photo.image_asset_key)
        for child in node.children:
            collect(child, parent_card)

    def walk(node: CleanDesignTreeNode, parent_card: CleanDesignTreeNode | None) -> None:
        parent_card = node if node.type == NodeType.CARD else parent_card
        signature = _product_photo_stack_signature(node, parent_card=parent_card)
        if signature is not None:
            photo = node.children[0]
            if not photo.image_asset_key:
                shared = signature_to_key.get(signature)
                if shared is not None:
                    photo.image_asset_key = shared
        for child in node.children:
            walk(child, parent_card)

    collect(tree, None)
    walk(tree, None)


def resolve_missing_image_asset_keys(
    tree: CleanDesignTreeNode,
    project_dir: Path,
) -> None:
    """Attach on-disk raster exports when the processed tree omitted ``imageAssetKey``."""
    from figma_flutter_agent.schemas import NodeType

    def walk(node: CleanDesignTreeNode) -> None:
        if (
            not node.image_asset_key
            and not node.children
            and node.type in {NodeType.CONTAINER, NodeType.IMAGE}
        ):
            discovered = discover_asset_path_for_node(project_dir, node.id)
            if discovered is not None:
                node.image_asset_key = discovered.replace("\\", "/")
        for child in node.children:
            walk(child)

    walk(tree)
    resolve_structural_duplicate_image_assets(tree)


def resolve_discovered_vector_asset_keys(
    tree: CleanDesignTreeNode,
    project_dir: Path,
) -> None:
    """Attach on-disk SVG exports when the clean tree omitted ``vectorAssetKey``.

    Offline dumps and deterministic re-emits often keep composite icon stacks
    (Google G, Facebook mark) without export metadata even though
    ``assets/icons/*_<node_id>.svg`` already exists in the Flutter project.

    Args:
        tree: Normalized clean tree (mutated in place).
        project_dir: Flutter project root containing ``assets/``.
    """
    from figma_flutter_agent.schemas import NodeType

    def walk(node: CleanDesignTreeNode) -> None:
        if not node.vector_asset_key and node.type in {
            NodeType.VECTOR,
            NodeType.STACK,
            NodeType.IMAGE,
        }:
            discovered = discover_asset_path_for_node(project_dir, node.id)
            if discovered is not None:
                node.vector_asset_key = discovered.replace("\\", "/")
        for child in node.children:
            walk(child)

    walk(tree)


def resolve_pruned_cluster_instance_assets(
    tree: CleanDesignTreeNode,
    project_dir: Path,
    manifest: AssetManifest | None = None,
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
        discovered = discover_asset_path_for_node(project_dir, node_id)
        if discovered and discovered not in paths:
            paths.append(discovered)
        return paths

    def walk(node: CleanDesignTreeNode) -> None:
        if node.cluster_id and not node.children:
            resolved: str | None = None
            for node_id in node.flatten_figma_node_ids or ():
                for candidate in candidate_paths(node_id):
                    if (project_dir / Path(candidate)).is_file():
                        resolved = candidate.replace("\\", "/")
                        break
                if resolved is not None:
                    break
            if resolved is None:
                for candidate in candidate_paths(node.id):
                    if (project_dir / Path(candidate)).is_file():
                        resolved = candidate.replace("\\", "/")
                        break
            if resolved is not None:
                node.vector_asset_key = resolved
        for child in node.children:
            walk(child)

    walk(tree)


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

    def walk(node: CleanDesignTreeNode) -> None:
        if not node.render_boundary:
            for child in node.children:
                walk(child)
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
        for child in node.children:
            walk(child)

    walk(tree)
    if unresolved:
        if strict:
            from figma_flutter_agent.errors import GenerationError

            raise GenerationError(
                "Render-boundary asset(s) missing on disk: "
                + ", ".join(sorted(unresolved))
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

    def walk(node: CleanDesignTreeNode) -> None:
        if node.render_boundary:
            export_ids.add(node.id)
            for flattened_id in node.flatten_figma_node_ids or ():
                exclude_ids.add(flattened_id)
        for child in node.children:
            walk(child)

    walk(root)
    return frozenset(export_ids), frozenset(exclude_ids)
