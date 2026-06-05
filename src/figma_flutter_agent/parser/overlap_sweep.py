"""Sweep-line overlap detection for Figma absolute-layout siblings."""

from __future__ import annotations

from dataclasses import dataclass

from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

Bounds = tuple[float, float, float, float]


@dataclass(frozen=True)
class PlacementRect:
    """Axis-aligned rectangle with a stable node id."""

    node_id: str
    left: float
    top: float
    right: float
    bottom: float

    @property
    def area(self) -> float:
        return max(0.0, self.right - self.left) * max(0.0, self.bottom - self.top)


@dataclass(frozen=True)
class OverlapPair:
    """Two siblings whose placements intersect."""

    first_id: str
    second_id: str
    intersection_area: float


def intersection_area(first: PlacementRect, second: PlacementRect) -> float:
    """Return overlap area between two placement rects."""
    ix0 = max(first.left, second.left)
    iy0 = max(first.top, second.top)
    ix1 = min(first.right, second.right)
    iy1 = min(first.bottom, second.bottom)
    if ix1 <= ix0 or iy1 <= iy0:
        return 0.0
    return (ix1 - ix0) * (iy1 - iy0)


def placement_rect_from_node(node: CleanDesignTreeNode) -> PlacementRect | None:
    """Build a placement rect from ``stack_placement`` when fully sized."""
    placement = node.stack_placement
    if placement is None:
        return None
    width = placement.width
    height = placement.height
    if width is None or height is None or width <= 0 or height <= 0:
        return None
    left = float(placement.left)
    top = float(placement.top)
    return PlacementRect(
        node_id=node.id,
        left=left,
        top=top,
        right=left + float(width),
        bottom=top + float(height),
    )


def sweep_overlapping_pairs(
    rects: list[PlacementRect],
    *,
    min_intersection: float = 1.0,
) -> list[OverlapPair]:
    """Find overlapping rect pairs using a vertical sweep (O(n log n))."""
    if len(rects) < 2:
        return []
    ordered = sorted(rects, key=lambda item: item.top)
    active: list[PlacementRect] = []
    pairs: list[OverlapPair] = []
    for current in ordered:
        active = [item for item in active if item.bottom > current.top]
        for other in active:
            area = intersection_area(current, other)
            if area >= min_intersection:
                pairs.append(
                    OverlapPair(
                        first_id=other.node_id,
                        second_id=current.node_id,
                        intersection_area=area,
                    )
                )
        active.append(current)
    return pairs


def cluster_overlapping_ids(
    pairs: list[OverlapPair],
) -> list[frozenset[str]]:
    """Group node ids that transitively overlap (union-find)."""
    parent: dict[str, str] = {}

    def find(node_id: str) -> str:
        parent.setdefault(node_id, node_id)
        while parent[node_id] != node_id:
            parent[node_id] = parent[parent[node_id]]
            node_id = parent[node_id]
        return node_id

    def union(first_id: str, second_id: str) -> None:
        root_a = find(first_id)
        root_b = find(second_id)
        if root_a != root_b:
            parent[root_b] = root_a

    for pair in pairs:
        union(pair.first_id, pair.second_id)

    groups: dict[str, set[str]] = {}
    for node_id in parent:
        root = find(node_id)
        groups.setdefault(root, set()).add(node_id)
    return [frozenset(group) for group in groups.values() if len(group) > 1]


def sibling_overlap_pairs(
    children: list[CleanDesignTreeNode],
    *,
    min_intersection: float = 1.0,
) -> list[OverlapPair]:
    """Return overlap pairs among positioned siblings."""
    rects: list[PlacementRect] = []
    for child in children:
        rect = placement_rect_from_node(child)
        if rect is not None:
            rects.append(rect)
    return sweep_overlapping_pairs(rects, min_intersection=min_intersection)


_INTERACTIVE_TYPES = frozenset(
    {
        NodeType.BUTTON,
        NodeType.INPUT,
        NodeType.TEXT,
        NodeType.CHECKBOX,
        NodeType.SWITCH,
        NodeType.RADIO,
        NodeType.SLIDER,
        NodeType.DROPDOWN,
    }
)
_OCCLUDER_TYPES = frozenset({NodeType.VECTOR, NodeType.IMAGE, NodeType.CONTAINER})


def _is_interactive(node: CleanDesignTreeNode) -> bool:
    return node.type in _INTERACTIVE_TYPES


def _is_opaque_occluder(node: CleanDesignTreeNode) -> bool:
    if node.type not in _OCCLUDER_TYPES:
        return False
    opacity = node.style.opacity
    if opacity is not None and opacity < 0.05:
        return False
    return True


def demote_overlapping_occluders(
    children: list[CleanDesignTreeNode],
) -> list[CleanDesignTreeNode]:
    """Move decorative siblings below interactives they overlap in stack paint order."""
    if len(children) < 2:
        return children
    flow = [child for child in children if child.stack_placement is None]
    positioned = [child for child in children if child.stack_placement is not None]
    if len(positioned) < 2:
        return children
    from figma_flutter_agent.parser.z_dag import z_dag_sort

    return [*flow, *z_dag_sort(positioned)]


def _node_area(node: CleanDesignTreeNode) -> float:
    width = node.sizing.width or 0.0
    height = node.sizing.height or 0.0
    placement = node.stack_placement
    if placement is not None:
        if placement.width is not None:
            width = placement.width
        if placement.height is not None:
            height = placement.height
    return width * height
