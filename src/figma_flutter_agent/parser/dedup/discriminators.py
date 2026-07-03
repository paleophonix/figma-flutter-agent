"""Role-band discriminators before structural bucket (04-P0-4 shadow)."""

from __future__ import annotations

from typing import Literal

from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

RoleBand = Literal["chrome", "icon_row", "content", "unknown"]


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


def discriminator_signature_component(node: CleanDesignTreeNode) -> str:
    """Return discriminator component for cluster signature shadow path."""
    return f"role:{classify_role_band(node)}"
