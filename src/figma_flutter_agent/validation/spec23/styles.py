"""Style synthesis criteria for spec-23."""

from __future__ import annotations

from typing import Any

from figma_flutter_agent.parser.styles import enrich_node_style
from figma_flutter_agent.parser.tree import build_clean_tree
from figma_flutter_agent.schemas import NodeStyle
from figma_flutter_agent.validation.spec23.models import Spec23CriterionResult


def _rest_style_from_fixture(root: dict[str, Any]) -> NodeStyle:
    """Return enriched style from the first node with REST-derived visual fields."""

    def walk(node: dict[str, Any]) -> NodeStyle | None:
        style = enrich_node_style(node, NodeStyle())
        if (
            style.background_color is not None
            or style.text_color is not None
            or style.border_radius is not None
            or style.font_size is not None
        ):
            return style
        for child in node.get("children") or []:
            if isinstance(child, dict):
                nested = walk(child)
                if nested is not None:
                    return nested
        return None

    return walk(root) or enrich_node_style(root, NodeStyle())


def _criterion_rest_css_synthesis(root: dict[str, Any], *, strict: bool) -> Spec23CriterionResult:
    """Validate REST-derived CSS-like properties (spec §5.1 strategy B)."""
    tree, _, _, _ = build_clean_tree(root)
    if strict:
        frame_style = _rest_style_from_fixture(root)
        passed = bool(tree.children) and (
            frame_style.background_color is not None
            or frame_style.text_color is not None
            or frame_style.border_radius is not None
            or frame_style.font_size is not None
        )
        detail = (
            f"REST style synthesis background={frame_style.background_color is not None} "
            "(not Figma Dev Mode API; see README Notes & limitations)"
        )
    else:
        passed = bool(tree.children)
        detail = f"REST style synthesis (root={tree.name})"
    return Spec23CriterionResult(name="rest_css_synthesis", passed=passed, detail=detail)
