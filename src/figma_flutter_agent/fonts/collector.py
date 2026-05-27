"""Collect required font faces from a clean design tree."""

from __future__ import annotations

from figma_flutter_agent.schemas import CleanDesignTreeNode, FontFaceRequirement, NodeType


def _walk(node: CleanDesignTreeNode) -> list[CleanDesignTreeNode]:
    nodes = [node]
    for child in node.children:
        nodes.extend(_walk(child))
    return nodes


def collect_font_faces(tree: CleanDesignTreeNode) -> list[FontFaceRequirement]:
    """Return unique font faces referenced by ``TEXT`` nodes in ``tree``."""
    seen: set[tuple[str, str, str | None]] = set()
    faces: list[FontFaceRequirement] = []
    for node in _walk(tree):
        if node.type != NodeType.TEXT:
            continue
        family = node.style.font_family
        if not family:
            continue
        weight = node.style.font_weight or "w400"
        style = node.style.font_style
        key = (family, weight, style)
        if key in seen:
            continue
        seen.add(key)
        faces.append(
            FontFaceRequirement(
                figma_family=family,
                font_weight=weight,
                font_style=style,
            )
        )
    return faces
