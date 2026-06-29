"""Rendering ambient and wallpaper layers."""

from __future__ import annotations

import re

from figma_flutter_agent.generator.layout.style import dart_color_expr
from figma_flutter_agent.generator.layout.widgets import (
    _apply_stack_position,
    _render_exported_vector,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

from .partition import _is_opaque_neutral_shell, collect_ambient_background_children

_TRANSPARENT_FILLS = frozenset({"0XFFFFFFFF", "0X00000000", None})


def render_ambient_decorative_node(
    node: CleanDesignTreeNode,
    *,
    uses_svg: bool,
    parent_type: NodeType | None = NodeType.STACK,
) -> str | None:
    """Render a decorative vector/image subtree without the full layout pipeline.

    Ambient layers must not call ``render_node_body`` (buttons, theme tokens, inputs).
    """
    if node.render_boundary and node.vector_asset_key:
        widget = _render_exported_vector(node, uses_svg=uses_svg)
        if widget is None:
            return None
        return _apply_stack_position(node, widget, parent_type=parent_type)

    if node.type == NodeType.VECTOR and node.vector_asset_key:
        widget = _render_exported_vector(node, uses_svg=uses_svg)
        if widget is None:
            return None
        return _apply_stack_position(node, widget, parent_type=parent_type)

    if node.type == NodeType.IMAGE and node.image_asset_key:
        widget = _render_exported_vector(node, uses_svg=uses_svg)
        if widget is None:
            return None
        return _apply_stack_position(node, widget, parent_type=parent_type)

    if node.type == NodeType.STACK:
        parts: list[str] = []
        for child in node.children:
            rendered = render_ambient_decorative_node(
                child,
                uses_svg=uses_svg,
                parent_type=NodeType.STACK,
            )
            if rendered:
                parts.append(rendered)
        if not parts:
            return None
        inner = f"Stack(clipBehavior: Clip.none, children: [{', '.join(parts)}])"
        return _apply_stack_position(node, inner, parent_type=parent_type)

    return None


def _collect_node_asset_keys(node: CleanDesignTreeNode) -> frozenset[str]:
    keys: set[str] = set()
    if node.vector_asset_key:
        keys.add(node.vector_asset_key)
    if node.image_asset_key:
        keys.add(node.image_asset_key)
    for child in node.children:
        keys.update(_collect_node_asset_keys(child))
    return frozenset(keys)


def _ambient_canvas_fill_expr(root: CleanDesignTreeNode) -> str | None:
    """Decorative vector fills belong in SVG layers, not a full-canvas ``ColoredBox``."""
    del root
    return None


def resolve_screen_canvas_background_expr(root: CleanDesignTreeNode) -> str | None:
    """Derive scaffold fill from the root frame only (not decorative ambient blobs)."""
    root_color = root.style.background_color
    if (
        root_color
        and root_color.upper() not in _TRANSPARENT_FILLS
        and not _is_opaque_neutral_shell(root_color)
    ):
        return dart_color_expr(root.style)
    return None


def patch_scaffold_background_from_tree(
    screen_code: str,
    root: CleanDesignTreeNode,
) -> str:
    """Align ``Scaffold`` background with the design canvas color from the tree."""
    fill_expr = resolve_screen_canvas_background_expr(root)
    if fill_expr is None:
        return screen_code
    if fill_expr.replace("const ", "") in screen_code:
        return screen_code
    updated, count = re.subn(
        r"backgroundColor:\s*const Color\(0xFFFFFFFF\)",
        f"backgroundColor: {fill_expr}",
        screen_code,
        count=1,
    )
    if count:
        return updated
    scaffold_match = re.search(
        r"(Scaffold\s*\([^)]*backgroundColor:\s*)([^,]+)",
        screen_code,
        re.DOTALL,
    )
    if scaffold_match is None:
        return screen_code
    return screen_code[: scaffold_match.start(2)] + fill_expr + screen_code[scaffold_match.end(2) :]


def render_wallpaper_artboard_stack_body(
    wallpaper_children: list[CleanDesignTreeNode],
    *,
    uses_svg: bool,
) -> str | None:
    """Render ambient wallpaper as the bottom layer of a bounded artboard stack."""
    bodies: list[str] = []
    for child in wallpaper_children:
        rendered = render_ambient_decorative_node(
            child,
            uses_svg=uses_svg,
            parent_type=NodeType.STACK,
        )
        if rendered:
            bodies.append(rendered)
    if not bodies:
        return None
    inner = f"Stack(clipBehavior: Clip.none, children: [{', '.join(bodies)}])"
    return f"IgnorePointer(child: RepaintBoundary(child: {inner}))"


def render_screen_wallpaper_layer(
    root: CleanDesignTreeNode,
    wallpaper_children: list[CleanDesignTreeNode],
    *,
    uses_svg: bool,
) -> str | None:
    """Render oversized illustration boundaries as a non-interactive cover layer."""
    width = root.sizing.width
    height = root.sizing.height
    if not wallpaper_children or width is None or height is None or width <= 0 or height <= 0:
        return None
    bodies: list[str] = []
    for child in wallpaper_children:
        rendered = render_ambient_decorative_node(
            child,
            uses_svg=uses_svg,
            parent_type=NodeType.STACK,
        )
        if rendered:
            bodies.append(rendered)
    if not bodies:
        return None
    width_token = f"{width:g}" if width != int(width) else str(int(width))
    height_token = f"{height:g}" if height != int(height) else str(int(height))
    stack_inner = (
        "Stack(\n"
        "                              clipBehavior: Clip.none,\n"
        f"                              children: [{', '.join(bodies)}],\n"
        "                            )"
    )
    return (
        "Positioned.fill(\n"
        "                    child: RepaintBoundary(\n"
        "                      child: IgnorePointer(\n"
        "                        child: FittedBox(\n"
        "                          fit: BoxFit.cover,\n"
        "                          clipBehavior: Clip.hardEdge,\n"
        "                          child: SizedBox(\n"
        f"                            width: {width_token},\n"
        f"                            height: {height_token},\n"
        f"                            child: {stack_inner},\n"
        "                          ),\n"
        "                        ),\n"
        "                      ),\n"
        "                    ),\n"
        "                  )"
    )


def render_ambient_background_layer(
    root: CleanDesignTreeNode,
    *,
    uses_svg: bool,
) -> str | None:
    """Render the cover-scaled ambient background ``Positioned.fill`` layer."""
    children = collect_ambient_background_children(root)
    width = root.sizing.width
    height = root.sizing.height
    if not children or width is None or height is None or width <= 0 or height <= 0:
        return None
    bodies: list[str] = []
    for child in children:
        rendered = render_ambient_decorative_node(
            child,
            uses_svg=uses_svg,
            parent_type=NodeType.STACK,
        )
        if rendered:
            bodies.append(rendered)
    if not bodies:
        return None
    width_token = f"{width:g}" if width != int(width) else str(int(width))
    height_token = f"{height:g}" if height != int(height) else str(int(height))
    stack_inner = (
        "Stack(\n"
        "                              clipBehavior: Clip.none,\n"
        f"                              children: [{', '.join(bodies)}],\n"
        "                            )"
    )
    return (
        "Positioned.fill(\n"
        "                    child: IgnorePointer(\n"
        "                      child: FittedBox(\n"
        "                        fit: BoxFit.cover,\n"
        "                        clipBehavior: Clip.hardEdge,\n"
        "                        child: SizedBox(\n"
        f"                          width: {width_token},\n"
        f"                          height: {height_token},\n"
        f"                          child: {stack_inner},\n"
        "                        ),\n"
        "                      ),\n"
        "                    ),\n"
        "                  )"
    )
