"""Axis-aligned box metrics: IoU, GIoU, DIoU and Figma-node tier thresholds."""

from __future__ import annotations

import math
from dataclasses import dataclass

from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType


@dataclass(frozen=True)
class BoxMetrics:
    """Spatial overlap metrics between expected (Figma) and runtime (Flutter) AABBs."""

    iou: float
    giou: float
    diou: float
    center_delta_x: float
    center_delta_y: float
    enclosing_diagonal_sq: float

    @property
    def center_distance(self) -> float:
        return math.hypot(self.center_delta_x, self.center_delta_y)


def _area(box: tuple[float, float, float, float]) -> float:
    left, top, width, height = box
    return max(0.0, width) * max(0.0, height)


def _intersection(
    a: tuple[float, float, float, float],
    b: tuple[float, float, float, float],
) -> float:
    al, at, aw, ah = a
    bl, bt, bw, bh = b
    ix0 = max(al, bl)
    iy0 = max(at, bt)
    ix1 = min(al + aw, bl + bw)
    iy1 = min(at + ah, bt + bh)
    if ix1 <= ix0 or iy1 <= iy0:
        return 0.0
    return (ix1 - ix0) * (iy1 - iy0)


def _enclosing_box(
    a: tuple[float, float, float, float],
    b: tuple[float, float, float, float],
) -> tuple[float, float, float, float]:
    al, at, aw, ah = a
    bl, bt, bw, bh = b
    left = min(al, bl)
    top = min(at, bt)
    right = max(al + aw, bl + bw)
    bottom = max(at + ah, bt + bh)
    return left, top, right - left, bottom - top


def _centers(box: tuple[float, float, float, float]) -> tuple[float, float]:
    left, top, width, height = box
    return left + width / 2.0, top + height / 2.0


def box_metrics(
    expected: tuple[float, float, float, float],
    runtime: tuple[float, float, float, float],
) -> BoxMetrics:
    """Compute IoU, GIoU, and DIoU for two axis-aligned boxes ``(left, top, w, h)``."""
    inter = _intersection(expected, runtime)
    union = _area(expected) + _area(runtime) - inter
    iou = inter / union if union > 0 else 0.0

    enc = _enclosing_box(expected, runtime)
    enc_area = _area(enc)
    giou = iou - (enc_area - union) / enc_area if enc_area > 0 else -1.0

    ecx, ecy = _centers(expected)
    rcx, rcy = _centers(runtime)
    delta_x = rcx - ecx
    delta_y = rcy - ecy
    enc_w, enc_h = enc[2], enc[3]
    c_sq = enc_w * enc_w + enc_h * enc_h
    diou = iou - (delta_x * delta_x + delta_y * delta_y) / c_sq if c_sq > 0 else -1.0

    return BoxMetrics(
        iou=iou,
        giou=giou,
        diou=diou,
        center_delta_x=delta_x,
        center_delta_y=delta_y,
        enclosing_diagonal_sq=c_sq,
    )


@dataclass(frozen=True)
class GeometryTierThresholds:
    """Hierarchical minimum GIoU by widget role (Fidelity Engine v2.0 §3.1)."""

    canvas: float = 0.99
    structural: float = 0.95
    component: float = 0.90
    leaf: float = 0.82

    def threshold_for_tier(self, tier: str) -> float:
        return {
            "canvas": self.canvas,
            "structural": self.structural,
            "component": self.component,
            "leaf": self.leaf,
        }.get(tier, self.component)


_STRUCTURAL_TYPES = frozenset(
    {
        NodeType.STACK,
        NodeType.COLUMN,
        NodeType.ROW,
        NodeType.WRAP,
        NodeType.GRID,
    }
)
_COMPONENT_TYPES = frozenset(
    {
        NodeType.BUTTON,
        NodeType.INPUT,
        NodeType.CARD,
        NodeType.CONTAINER,
        NodeType.TABS,
        NodeType.BOTTOM_NAV,
    }
)
_LEAF_TYPES = frozenset(
    {
        NodeType.TEXT,
        NodeType.VECTOR,
        NodeType.IMAGE,
        NodeType.CHECKBOX,
        NodeType.SWITCH,
        NodeType.RADIO,
    }
)


def geometry_tier_for_node(
    node: CleanDesignTreeNode,
    *,
    root_id: str,
    depth: int = 0,
) -> str:
    """Classify a clean-tree node for hierarchical geometry tolerance."""
    if node.id == root_id or depth == 0:
        return "canvas"
    if node.type in _LEAF_TYPES:
        return "leaf"
    if node.type in _COMPONENT_TYPES:
        return "component"
    if node.type in _STRUCTURAL_TYPES:
        return "structural"
    if depth <= 2:
        return "structural"
    return "component"


def node_depth(
    node_id: str,
    *,
    parent_by_id: dict[str, str],
) -> int:
    depth = 0
    current = parent_by_id.get(node_id)
    while current is not None:
        depth += 1
        current = parent_by_id.get(current)
    return depth


def build_parent_map(root: CleanDesignTreeNode) -> dict[str, str]:
    parents: dict[str, str] = {}

    def walk(node: CleanDesignTreeNode, parent_id: str | None) -> None:
        if parent_id is not None:
            parents[node.id] = parent_id
        for child in node.children:
            walk(child, node.id)

    walk(root, None)
    return parents


def passes_geometry_threshold(metrics: BoxMetrics, min_giou: float) -> bool:
    """Pass when generalized IoU meets the tier threshold."""
    return metrics.giou >= min_giou
