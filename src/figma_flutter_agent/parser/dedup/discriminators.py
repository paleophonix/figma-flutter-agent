"""Role-band discriminators before structural bucket (04-P0-4 shadow)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

RoleBand = Literal["chrome", "icon_row", "content", "unknown"]


@dataclass(frozen=True, slots=True)
class ClusterDiscriminator:
    """Shadow signature components from independent source facts only (no ownership overlay)."""

    viewport_region: str | None
    anchor_role: str | None
    interaction_role: str | None
    role_band: RoleBand


def classify_role_band(node: CleanDesignTreeNode) -> RoleBand:
    """Shadow discriminator: coarse role band for cluster signature (report-only P0)."""
    if node.type in {NodeType.BOTTOM_NAV, NodeType.TABS}:
        return "chrome"
    name = (node.name or "").lower()
    if "status" in name and "bar" in name:
        return "chrome"
    if "tab" in name and "bar" in name:
        return "chrome"
    child_types = {child.type for child in node.children}
    if NodeType.VECTOR in child_types and len(node.children) <= 4:
        vector_children = sum(1 for c in node.children if c.type == NodeType.VECTOR)
        if vector_children >= 2:
            return "icon_row"
    return "content"


def build_cluster_discriminator(node: CleanDesignTreeNode) -> ClusterDiscriminator:
    """Build shadow discriminator from geometry/name facts — not Program 05 overlay."""
    interaction_role: str | None = None
    if node.type in {NodeType.BUTTON, NodeType.INPUT, NodeType.CHECKBOX}:
        interaction_role = node.type.value.lower()
    return ClusterDiscriminator(
        viewport_region=getattr(node, "layout_region", None),
        anchor_role=(node.stack_placement.horizontal if node.stack_placement else None),
        interaction_role=interaction_role,
        role_band=classify_role_band(node),
    )


def discriminator_signature_component(node: CleanDesignTreeNode) -> str:
    """Return discriminator component for cluster signature shadow path."""
    disc = build_cluster_discriminator(node)
    return (
        f"role:{disc.role_band}|anchor:{disc.anchor_role}|interaction:{disc.interaction_role}"
    )
