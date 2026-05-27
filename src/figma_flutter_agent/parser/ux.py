"""UX quality heuristics for generated Flutter layouts."""

from __future__ import annotations

from figma_flutter_agent.errors import GenerationError
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType, SizingMode

_MIN_TOUCH_TARGET = 48.0
_MAX_LAYOUT_DEPTH = 8
_MAX_SPACING_VARIANTS = 6


def _tree_depth(node: CleanDesignTreeNode, current: int = 1) -> int:
    if not node.children:
        return current
    return max(_tree_depth(child, current + 1) for child in node.children)


def _collect_touch_targets(node: CleanDesignTreeNode) -> list[CleanDesignTreeNode]:
    targets: list[CleanDesignTreeNode] = []
    if node.type in {NodeType.BUTTON, NodeType.INPUT}:
        targets.append(node)
    for child in node.children:
        targets.extend(_collect_touch_targets(child))
    return targets


def _is_undersized_target(node: CleanDesignTreeNode) -> bool:
    width = node.sizing.width
    height = node.sizing.height
    return (
        (width is not None and width < _MIN_TOUCH_TARGET)
        or (height is not None and height < _MIN_TOUCH_TARGET)
        or (
            node.sizing.width_mode == SizingMode.FIXED
            and node.sizing.height_mode == SizingMode.FIXED
            and width is not None
            and height is not None
            and width < _MIN_TOUCH_TARGET
            and height < _MIN_TOUCH_TARGET
        )
    )


def _collect_spacing_values(node: CleanDesignTreeNode) -> set[float]:
    values = {node.spacing}
    values.update(
        value
        for value in (
            node.padding.top,
            node.padding.right,
            node.padding.bottom,
            node.padding.left,
        )
        if value > 0
    )
    for child in node.children:
        values.update(_collect_spacing_values(child))
    return values


def enforce_ux_gates(
    root: CleanDesignTreeNode, *, max_layout_depth: int = _MAX_LAYOUT_DEPTH
) -> None:
    """Raise when spec §9 layout depth gate is violated.

    Args:
        root: Parsed clean design tree.
        max_layout_depth: Maximum allowed nesting depth.

    Raises:
        GenerationError: When layout depth exceeds ``max_layout_depth``.
    """
    depth = _tree_depth(root)
    if depth > max_layout_depth:
        raise GenerationError(
            f"Layout nesting depth {depth} exceeds limit {max_layout_depth} (spec §9)"
        )


def collect_ux_suggestions(root: CleanDesignTreeNode) -> list[str]:
    """Collect non-fatal UX improvement suggestions from a clean design tree."""
    suggestions: list[str] = []

    depth = _tree_depth(root)
    if depth > _MAX_LAYOUT_DEPTH:
        suggestions.append(
            f"Layout nesting depth is {depth}; consider flattening groups for simpler Flutter widget trees."
        )

    spacing_values = _collect_spacing_values(root)
    if len(spacing_values) > _MAX_SPACING_VARIANTS:
        suggestions.append(
            f"Found {len(spacing_values)} distinct spacing values; align to design tokens for consistency."
        )

    undersized = [node for node in _collect_touch_targets(root) if _is_undersized_target(node)]
    if undersized:
        names = ", ".join(node.name for node in undersized[:3])
        suggestions.append(
            f"{len(undersized)} interactive nodes may be below 48dp touch targets: {names}"
        )

    fill_count = 0
    total_count = 0

    def count_fill_nodes(node: CleanDesignTreeNode) -> None:
        nonlocal fill_count, total_count
        total_count += 1
        if node.sizing.width_mode == SizingMode.FILL or node.sizing.height_mode == SizingMode.FILL:
            fill_count += 1
        for child in node.children:
            count_fill_nodes(child)

    count_fill_nodes(root)
    if total_count >= 10 and fill_count == 0:
        suggestions.append(
            "No FILL-sized nodes detected; verify Auto Layout constraints map to responsive Flutter widgets."
        )

    return suggestions
