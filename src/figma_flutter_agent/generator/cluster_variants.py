"""Detect parameterized variants for extracted cluster widgets."""

from __future__ import annotations

from dataclasses import dataclass

from figma_flutter_agent.schemas import CleanDesignTreeNode


@dataclass(frozen=True)
class ClusterVectorVariant:
    """Two mirrored vector assets inside the same structural cluster."""

    cluster_id: str
    forward_asset: str
    backward_asset: str
    param_name: str = "isForward"


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
            asset = primary_vector_asset(node)
            if asset is not None:
                assets.add(asset)
        for child in node.children:
            walk(child)

    for tree in trees:
        walk(tree)
    return assets


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


def cluster_reference_args(
    node: CleanDesignTreeNode,
    variant: ClusterVectorVariant,
) -> str:
    """Build constructor args for a cluster widget reference."""
    asset = primary_vector_asset(node)
    if asset == variant.backward_asset:
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
