"""Collect required font faces from a clean design tree."""

from __future__ import annotations

from typing import Any

from figma_flutter_agent.parser.typography import (
    resolve_font_family,
    resolve_font_style,
    resolve_font_weight,
)
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


def _append_face(
    faces: list[FontFaceRequirement],
    seen: set[tuple[str, str, str | None]],
    *,
    family: str | None,
    weight: str | None,
    style: str | None,
) -> None:
    if not family:
        return
    token = weight or "w400"
    key = (family, token, style)
    if key in seen:
        return
    seen.add(key)
    faces.append(
        FontFaceRequirement(
            figma_family=family,
            font_weight=token,
            font_style=style,
        )
    )


def collect_font_faces_from_figma_document(document: dict[str, Any]) -> list[FontFaceRequirement]:
    """Collect unique font faces from a raw Figma frame ``document`` subtree."""
    faces: list[FontFaceRequirement] = []
    seen: set[tuple[str, str, str | None]] = set()

    def walk(node: dict[str, Any]) -> None:
        if node.get("type") == "TEXT":
            style_obj = node.get("style")
            if isinstance(style_obj, dict):
                _append_face(
                    faces,
                    seen,
                    family=resolve_font_family(style_obj),
                    weight=resolve_font_weight(style_obj),
                    style=resolve_font_style(style_obj),
                )
        for child in node.get("children") or []:
            if isinstance(child, dict):
                walk(child)

    walk(document)
    return faces
