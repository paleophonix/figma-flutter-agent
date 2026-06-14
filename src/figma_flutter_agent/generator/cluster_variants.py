"""Detect parameterized variants for extracted cluster widgets."""

from __future__ import annotations

import re
from dataclasses import dataclass

from figma_flutter_agent.schemas import CleanDesignTreeNode

_SKIP_FORWARD_BACKWARD_PAIRS: dict[str, str] = {
    "assets/icons/vector_1_4017.svg": "assets/icons/vector_1_4020.svg",
}


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


def infer_backward_skip_asset(forward_asset: str) -> str | None:
    """Infer the mirrored skip icon export when only the forward asset survived parsing."""
    return _SKIP_FORWARD_BACKWARD_PAIRS.get(forward_asset)


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


def resolve_cluster_delegate_class(
    node: CleanDesignTreeNode,
    cluster_classes: dict[str, str] | None,
    *,
    skip_cluster_id: str | None = None,
) -> str | None:
    """Resolve a cluster widget class for structural or component-family clusters."""
    if not cluster_classes:
        return None
    keys: list[str] = []
    if node.cluster_id:
        keys.append(node.cluster_id)
    component_id = component_id_for_node(node)
    if component_id:
        from figma_flutter_agent.parser.dedup.clusters import component_cluster_id

        keys.append(component_cluster_id(component_id))
    for key in keys:
        if key == skip_cluster_id:
            continue
        class_name = cluster_classes.get(key)
        if class_name:
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
) -> ClusterVectorVariant | None:
    """Detect forward/backward vector variants for a repeated cluster.

    Args:
        trees: Parsed clean design trees for the screen batch.
        cluster_id: Structural cluster identifier.
        representative: Representative cluster node; its vector asset becomes ``forward``.

    Returns:
        Variant metadata when the cluster uses exactly two distinct vector assets.
    """
    assets = sorted(_collect_cluster_assets(trees, cluster_id))
    if len(assets) == 1 and _cluster_has_mirror_skip_placements(trees, cluster_id):
        inferred = infer_backward_skip_asset(assets[0])
        if inferred is not None:
            forward_asset = assets[0]
            backward_asset = inferred
            if representative is not None:
                rep_asset = primary_vector_asset(representative) or representative.vector_asset_key
                if rep_asset == inferred:
                    forward_asset, backward_asset = inferred, assets[0]
            return ClusterVectorVariant(
                cluster_id=cluster_id,
                forward_asset=forward_asset,
                backward_asset=backward_asset,
            )
    if len(assets) != 2:
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
) -> dict[str, ClusterVectorVariant]:
    """Return vector flip variants for clusters that need parameterized widgets."""
    variants: dict[str, ClusterVectorVariant] = {}
    for cluster_id, representative in sorted(representatives.items()):
        variant = detect_vector_flip_variant(
            trees,
            cluster_id,
            representative=representative,
        )
        if variant is not None:
            variants[cluster_id] = variant
    return variants


def cluster_uses_chip_variant_labels(
    trees: list[CleanDesignTreeNode],
    cluster_id: str,
) -> bool:
    """Return True when any cluster member carries a ``Text#`` variant label."""
    from figma_flutter_agent.parser.interaction.chip_variant import chip_component_label

    found = False

    def walk(node: CleanDesignTreeNode) -> None:
        nonlocal found
        if found:
            return
        if node.cluster_id == cluster_id and chip_component_label(node):
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
        chip_component_selected,
    )

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
