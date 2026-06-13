"""Semantic Z-band ordering for stack paint (T5-z)."""

from __future__ import annotations

from figma_flutter_agent.parser.interaction import stack_interaction_kind
from figma_flutter_agent.parser.overlap_sweep import sibling_overlap_pairs
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

_PRESENTATIONAL_TYPES = frozenset({NodeType.VECTOR, NodeType.IMAGE, NodeType.CONTAINER})
_INTERACTIVE_TYPES = frozenset(
    {
        NodeType.BUTTON,
        NodeType.INPUT,
        NodeType.CHECKBOX,
        NodeType.SWITCH,
        NodeType.RADIO,
        NodeType.DROPDOWN,
        NodeType.SLIDER,
        NodeType.BOTTOM_NAV,
    }
)


def _is_presentational(node: CleanDesignTreeNode) -> bool:
    if _is_interactive(node):
        return False
    if node.render_boundary:
        return True
    if node.type in _PRESENTATIONAL_TYPES and stack_interaction_kind(node) != "button":
        opacity = node.style.opacity
        return not (opacity is not None and opacity < 0.05)
    return False


def _is_interactive(node: CleanDesignTreeNode) -> bool:
    if node.type in _INTERACTIVE_TYPES:
        return True
    return stack_interaction_kind(node) == "button"


def semantic_z_band(node: CleanDesignTreeNode) -> int:
    """Return semantic paint band (lower paints first / below)."""
    if node.render_boundary and _is_presentational(node):
        return 0
    if _is_presentational(node) and not _is_interactive(node):
        return 1
    if _is_interactive(node):
        return 2
    if node.type in {NodeType.DIALOG}:
        return 3
    return 1


def semantic_z_sort(children: list[CleanDesignTreeNode]) -> list[CleanDesignTreeNode]:
    """Stable sort stack children by semantic Z-band then sibling index."""
    if len(children) < 2:
        return children
    indexed = list(enumerate(children))
    indexed.sort(key=lambda item: (semantic_z_band(item[1]), item[0]))
    ordered = [child for _, child in indexed]
    return _enforce_overlap_invariant(ordered)


def _enforce_overlap_invariant(children: list[CleanDesignTreeNode]) -> list[CleanDesignTreeNode]:
    """Ensure decor nodes paint below overlapping interactives."""
    if len(children) < 2:
        return children
    pairs = sibling_overlap_pairs(children)
    if not pairs:
        return children
    order = list(children)
    by_id = {child.id: child for child in children}
    changed = True
    while changed:
        changed = False
        for pair in pairs:
            first = by_id.get(pair.first_id)
            second = by_id.get(pair.second_id)
            if first is None or second is None:
                continue
            try:
                idx_first = order.index(first)
                idx_second = order.index(second)
            except ValueError:
                continue
            decor = interactive = None
            decor_idx = interactive_idx = -1
            if _is_presentational(first) and _is_interactive(second):
                decor, interactive = first, second
                decor_idx, interactive_idx = idx_first, idx_second
            elif _is_presentational(second) and _is_interactive(first):
                decor, interactive = second, first
                decor_idx, interactive_idx = idx_second, idx_first
            if decor is None or interactive is None:
                continue
            if decor_idx > interactive_idx:
                order.pop(decor_idx)
                order.insert(interactive_idx, decor)
                changed = True
    return order
