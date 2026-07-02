"""Detect parameterized variants for extracted cluster widgets."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from figma_flutter_agent.schemas import CleanDesignTreeNode


def _sizing_like_skip_control(node: CleanDesignTreeNode) -> bool:
    width = node.sizing.width
    height = node.sizing.height
    if width is None or height is None:
        return False
    return 28.0 <= width <= 56.0 and 28.0 <= height <= 56.0


def cluster_skip_backward_by_placement(node: CleanDesignTreeNode) -> bool:
    """True when absolute placement anchors the control on the screen's left side."""
    from figma_flutter_agent.parser.interaction import skip_control_left_side_of_parent

    return skip_control_left_side_of_parent(node)


def _cluster_member_figma_ids(node: CleanDesignTreeNode) -> list[str]:
    """Return figma node ids to probe for on-disk vector exports on a cluster member."""
    ids: list[str] = []
    seen: set[str] = set()

    def add(node_id: str | None) -> None:
        if node_id and node_id not in seen:
            seen.add(node_id)
            ids.append(node_id)

    add(node.id)
    for node_id in node.flatten_figma_node_ids or ():
        add(node_id)

    def walk(current: CleanDesignTreeNode) -> None:
        add(current.id)
        for child in current.children:
            walk(child)

    walk(node)
    return ids


def _discover_vector_assets_for_node(
    node: CleanDesignTreeNode,
    project_dir: Path | None,
) -> set[str]:
    """Collect vector asset keys from a cluster member and optional on-disk exports."""
    assets: set[str] = set()
    asset = primary_vector_asset(node) or node.vector_asset_key
    if asset is not None:
        assets.add(asset)
    if project_dir is None:
        return assets
    from figma_flutter_agent.parser.boundaries.assets import discover_asset_path_for_node

    for node_id in _cluster_member_figma_ids(node):
        discovered = discover_asset_path_for_node(project_dir, node_id)
        if discovered is not None:
            assets.add(discovered.replace("\\", "/"))
    return assets


def precollect_cluster_vector_assets(
    trees: list[CleanDesignTreeNode],
    *,
    project_dir: Path | None = None,
) -> dict[str, tuple[str | None, str | None]]:
    """Build forward/backward vector asset pairs per cluster before pruned stubs lose exports."""
    pairs: dict[str, tuple[str | None, str | None]] = {}

    def walk(node: CleanDesignTreeNode, parent: CleanDesignTreeNode | None) -> None:
        cluster_id = node.cluster_id
        if cluster_id:
            from figma_flutter_agent.parser.dedup.prune import _cluster_instance_is_backward

            parent_width = parent.sizing.width if parent is not None else None
            is_backward = _cluster_instance_is_backward(node, parent_width=parent_width)
            forward, backward = pairs.get(cluster_id, (None, None))
            for asset in _discover_vector_assets_for_node(node, project_dir):
                if is_backward:
                    backward = asset
                else:
                    forward = asset
            pairs[cluster_id] = (forward, backward)
        for child in node.children:
            walk(child, node)

    for tree in trees:
        walk(tree, None)
    return pairs


def _pair_from_precollected(
    precollected: dict[str, tuple[str | None, str | None]],
    cluster_id: str,
) -> tuple[str | None, str | None] | None:
    forward, backward = precollected.get(cluster_id, (None, None))
    if forward is None or backward is None or forward == backward:
        return None
    return forward, backward


@dataclass(frozen=True)
class ClusterVectorVariant:
    """Two mirrored vector assets inside the same structural cluster."""

    cluster_id: str
    forward_asset: str
    backward_asset: str
    param_name: str = "isForward"


def component_id_for_node(node: CleanDesignTreeNode) -> str | None:
    """Return the published Figma component id backing a clean-tree node."""
    if node.component_ref:
        return node.component_ref
    if node.variant is not None and node.variant.component_id:
        return node.variant.component_id
    return None


def _component_cluster_base_id(cluster_id: str) -> str | None:
    """Return ``component_<file>_<node>`` prefix for fingerprinted component cluster ids."""
    if not cluster_id.startswith("component_"):
        return None
    parts = cluster_id.split("_")
    if len(parts) < 3:
        return None
    return "_".join(parts[:3])


def _expand_skip_cluster_ids(
    skip_cluster_id: str | None,
    cluster_classes: dict[str, str],
) -> set[str]:
    """Block every cluster alias for the same published component family as ``skip_cluster_id``."""
    if skip_cluster_id is None:
        return set()
    blocked = {skip_cluster_id}
    base = _component_cluster_base_id(skip_cluster_id)
    if base is None:
        return blocked
    blocked.add(base)
    prefix = f"{base}_"
    blocked.update(
        cluster_id
        for cluster_id in cluster_classes
        if cluster_id == base or cluster_id.startswith(prefix)
    )
    return blocked


def cluster_classes_for_inline_widget_render(
    class_name: str,
    cluster_classes: dict[str, str] | None,
) -> dict[str, str] | None:
    """Keep only cluster delegates owned by the widget file being materialized inline."""
    if not cluster_classes:
        return None
    filtered = {
        cluster_id: mapped
        for cluster_id, mapped in cluster_classes.items()
        if mapped == class_name
    }
    return filtered or None


def _cluster_delegate_lookup_keys(node: CleanDesignTreeNode) -> list[str]:
    """Return cluster map keys in preferred lookup order for delegate resolution."""
    keys: list[str] = []
    if node.cluster_id:
        keys.append(node.cluster_id)
    component_id = component_id_for_node(node)
    if component_id:
        from figma_flutter_agent.parser.dedup.clusters import component_cluster_id
        from figma_flutter_agent.parser.dedup.signatures import descendant_text_fingerprint

        fingerprinted = component_cluster_id(
            component_id,
            text_fingerprint=descendant_text_fingerprint(node),
        )
        if fingerprinted not in keys:
            keys.append(fingerprinted)
        base = component_cluster_id(component_id)
        if fingerprinted == base and base not in keys:
            keys.append(base)
    return keys


def resolve_cluster_delegate_class(
    node: CleanDesignTreeNode,
    cluster_classes: dict[str, str] | None,
    *,
    skip_cluster_id: str | None = None,
) -> str | None:
    """Resolve a cluster widget class for structural or component-family clusters."""
    if not cluster_classes:
        return None
    if (
        node.cluster_id is not None
        and not node.children
        and bool(node.flatten_figma_node_ids)
        and bool(node.vector_asset_key)
        and node.component_ref is None
    ):
        return None
    blocked_cluster_ids = _expand_skip_cluster_ids(skip_cluster_id, cluster_classes)
    blocked_class_names = {
        cluster_classes[cluster_id]
        for cluster_id in blocked_cluster_ids
        if cluster_id in cluster_classes
    }
    for key in _cluster_delegate_lookup_keys(node):
        if key in blocked_cluster_ids:
            continue
        class_name = cluster_classes.get(key)
        if class_name and class_name not in blocked_class_names:
            return class_name
    return None


def primary_vector_asset(node: CleanDesignTreeNode) -> str | None:
    """Return the first exported vector asset key inside ``node``."""
    if node.vector_asset_key:
        return node.vector_asset_key
    for child in node.children:
        asset = primary_vector_asset(child)
        if asset is not None:
            return asset
    return None


def _collect_cluster_assets(
    trees: list[CleanDesignTreeNode],
    cluster_id: str,
) -> set[str]:
    assets: set[str] = set()

    def walk(node: CleanDesignTreeNode) -> None:
        if node.cluster_id == cluster_id:
            asset = primary_vector_asset(node) or node.vector_asset_key
            if asset is not None:
                assets.add(asset)
        for child in node.children:
            walk(child)

    for tree in trees:
        walk(tree)
    return assets


def _cluster_has_mirror_skip_placements(
    trees: list[CleanDesignTreeNode],
    cluster_id: str,
) -> bool:
    backward = False
    forward = False

    def walk(node: CleanDesignTreeNode) -> None:
        nonlocal backward, forward
        if node.cluster_id == cluster_id and _sizing_like_skip_control(node):
            if cluster_skip_backward_by_placement(node):
                backward = True
            else:
                forward = True
        for child in node.children:
            walk(child)

    for tree in trees:
        walk(tree)
    return backward and forward


def detect_vector_flip_variant(
    trees: list[CleanDesignTreeNode],
    cluster_id: str,
    *,
    representative: CleanDesignTreeNode | None = None,
    project_dir: Path | None = None,
    precollected_assets: dict[str, tuple[str | None, str | None]] | None = None,
) -> ClusterVectorVariant | None:
    """Detect forward/backward vector variants for a repeated cluster.

    Args:
        trees: Parsed clean design trees for the screen batch.
        cluster_id: Structural cluster identifier.
        representative: Representative cluster node; its vector asset becomes ``forward``.
        project_dir: Optional Flutter project root for on-disk SVG discovery.
        precollected_assets: Optional per-cluster forward/backward asset pairs.

    Returns:
        Variant metadata when the cluster uses exactly two distinct vector assets.
    """
    precollected = precollected_assets or precollect_cluster_vector_assets(
        trees,
        project_dir=project_dir,
    )
    assets = sorted(_collect_cluster_assets(trees, cluster_id))
    if len(assets) == 1 and _cluster_has_mirror_skip_placements(trees, cluster_id):
        paired = _pair_from_precollected(precollected, cluster_id)
        if paired is not None:
            forward_asset, backward_asset = paired
            if representative is not None:
                rep_asset = primary_vector_asset(representative) or representative.vector_asset_key
                if rep_asset == backward_asset:
                    forward_asset, backward_asset = backward_asset, forward_asset
                elif rep_asset == forward_asset:
                    pass
                elif rep_asset in {forward_asset, backward_asset}:
                    forward_asset = rep_asset
                    backward_asset = (
                        backward_asset if forward_asset != backward_asset else forward_asset
                    )
            return ClusterVectorVariant(
                cluster_id=cluster_id,
                forward_asset=forward_asset,
                backward_asset=backward_asset,
            )
    if len(assets) != 2:
        paired = _pair_from_precollected(precollected, cluster_id)
        if paired is not None and _cluster_has_mirror_skip_placements(trees, cluster_id):
            forward_asset, backward_asset = paired
            return ClusterVectorVariant(
                cluster_id=cluster_id,
                forward_asset=forward_asset,
                backward_asset=backward_asset,
            )
        return None
    forward_asset = assets[0]
    backward_asset = assets[1]
    if representative is not None:
        rep_asset = primary_vector_asset(representative)
        if rep_asset in assets:
            forward_asset = rep_asset
            backward_asset = assets[1] if assets[0] == rep_asset else assets[0]
    return ClusterVectorVariant(
        cluster_id=cluster_id,
        forward_asset=forward_asset,
        backward_asset=backward_asset,
    )


def restore_pruned_cluster_vector_keys(
    root: CleanDesignTreeNode,
    variants: dict[str, ClusterVectorVariant],
) -> None:
    """Set ``vector_asset_key`` on pruned duplicate cluster nodes (processed dumps)."""

    def walk(node: CleanDesignTreeNode) -> None:
        variant = variants.get(node.cluster_id) if node.cluster_id else None
        if variant is not None and not node.children and not node.vector_asset_key:
            placement = node.stack_placement
            left = placement.left if placement is not None and placement.left is not None else 0.0
            if left < 120.0:
                node.vector_asset_key = variant.backward_asset
            else:
                node.vector_asset_key = variant.forward_asset
        for child in node.children:
            walk(child)

    walk(root)


def collect_cluster_vector_variants(
    trees: list[CleanDesignTreeNode],
    representatives: dict[str, CleanDesignTreeNode],
    *,
    project_dir: Path | None = None,
) -> dict[str, ClusterVectorVariant]:
    """Return vector flip variants for clusters that need parameterized widgets."""
    precollected = precollect_cluster_vector_assets(trees, project_dir=project_dir)
    variants: dict[str, ClusterVectorVariant] = {}
    for cluster_id, representative in sorted(representatives.items()):
        variant = detect_vector_flip_variant(
            trees,
            cluster_id,
            representative=representative,
            project_dir=project_dir,
            precollected_assets=precollected,
        )
        if variant is not None:
            variants[cluster_id] = variant
    return variants


def cluster_uses_chip_variant_labels(
    trees: list[CleanDesignTreeNode],
    cluster_id: str,
) -> bool:
    """Return True when any tag chip row in the cluster carries a ``Text#`` label axis."""
    from figma_flutter_agent.parser.interaction.chip_variant import (
        chip_component_label,
        is_tag_component_chip_row,
    )

    found = False

    def walk(node: CleanDesignTreeNode) -> None:
        nonlocal found
        if found:
            return
        if (
            node.cluster_id == cluster_id
            and is_tag_component_chip_row(node)
            and chip_component_label(node)
        ):
            found = True
            return
        for child in node.children:
            walk(child)

    for tree in trees:
        walk(tree)
    return found


def cluster_chip_reference_args(node: CleanDesignTreeNode) -> str | None:
    """Build constructor args for parameterized chip cluster widgets."""
    from figma_flutter_agent.generator.layout.common import escape_dart_string
    from figma_flutter_agent.parser.interaction.chip_variant import (
        chip_component_display_label,
        chip_component_label,
        chip_component_selected,
        is_tag_component_chip_row,
    )

    if not is_tag_component_chip_row(node) or not chip_component_label(node):
        return None
    label = chip_component_display_label(node)
    if not label:
        return None
    parts = [f"label: '{escape_dart_string(label)}'"]
    if chip_component_selected(node):
        parts.append("isSelected: true")
    else:
        parts.append("isSelected: false")
    return ", ".join(parts)


def chip_label_widget_defaults(
    representative: CleanDesignTreeNode,
) -> tuple[str, bool]:
    """Return default ``label`` and ``isSelected`` for a chip cluster widget."""
    from figma_flutter_agent.generator.layout.common import escape_dart_string
    from figma_flutter_agent.parser.interaction.chip_variant import chip_component_display_label

    label = chip_component_display_label(representative)
    if not label:
        label = representative.name or "Chip"
    return escape_dart_string(label), False


def parameterize_chip_label_widget_body(
    body: str,
    default_label: str,
) -> str:
    """Replace the representative label literal with the ``label`` parameter."""
    quoted = re.escape(default_label)
    pattern = rf"Text\('{quoted}'"
    updated, count = re.subn(pattern, "Text(label", body, count=1)
    if count:
        return updated
    lower_pattern = rf"Text\('{re.escape(default_label.lower())}'"
    return re.sub(lower_pattern, "Text(label", body, count=1)


def parameterize_chip_hug_width_widget_body(body: str) -> str:
    """Strip representative fixed width from chip widget bodies (keep height)."""
    return re.sub(
        r"SizedBox\(width: [^,]+, height: ([^,]+), child: ",
        r"SizedBox(height: \1, child: ",
        body,
        count=1,
    )


def cluster_reference_args(
    node: CleanDesignTreeNode,
    variant: ClusterVectorVariant,
) -> str:
    """Build constructor args for a cluster widget reference."""
    asset = primary_vector_asset(node) or node.vector_asset_key
    if asset == variant.backward_asset:
        return f"{variant.param_name}: false"
    if asset == variant.forward_asset:
        return ""
    if cluster_skip_backward_by_placement(node):
        return f"{variant.param_name}: false"
    return ""


def cluster_uses_variant(
    node: CleanDesignTreeNode,
    variant: ClusterVectorVariant,
) -> bool:
    """Return True when ``node`` belongs to a vector-flip cluster variant."""
    if node.cluster_id != variant.cluster_id:
        return False
    asset = primary_vector_asset(node)
    return asset in {variant.forward_asset, variant.backward_asset}
