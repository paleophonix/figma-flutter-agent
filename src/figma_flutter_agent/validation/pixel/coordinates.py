"""TEXT coordinate validation for visual comparison."""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType
from figma_flutter_agent.validation.iou import _design_canvas_size, _placement_box, _scale_box
from figma_flutter_agent.validation.pixel.models import (
    DictFlutterCoordinateMapper,
    FlutterCoordinateMapper,
    TextCoordinateFailure,
    TextCoordinateValidationResult,
)


def parse_flutter_mapper_payload(
    payload: Mapping[str, object] | None,
) -> DictFlutterCoordinateMapper | None:
    """Build a mapper from ``{token: {left, top, width, height}}`` golden JSON."""
    if not payload:
        return None
    rects: dict[str, tuple[float, float, float, float]] = {}
    for token, raw in payload.items():
        if not isinstance(raw, Mapping):
            continue
        try:
            rects[str(token)] = (
                float(raw["left"]),
                float(raw["top"]),
                float(raw["width"]),
                float(raw["height"]),
            )
        except (KeyError, TypeError, ValueError):
            continue
    if not rects:
        return None
    return DictFlutterCoordinateMapper(rects_by_token=rects)


def iter_text_nodes(root: CleanDesignTreeNode) -> Iterable[CleanDesignTreeNode]:
    """Yield TEXT nodes in depth-first order."""
    if root.type == NodeType.TEXT:
        yield root
    for child in root.children:
        yield from iter_text_nodes(child)


def figma_text_box(
    node: CleanDesignTreeNode,
    *,
    design_width: float,
    design_height: float,
    image_width: int,
    image_height: int,
) -> tuple[int, int, int, int] | None:
    placement = node.stack_placement
    if placement is None:
        return None
    box = _placement_box(placement)
    if box is None:
        return None
    x0, y0, width, height = _scale_box(
        box,
        design_width=design_width,
        design_height=design_height,
        image_width=image_width,
        image_height=image_height,
    )
    if width <= 0 or height <= 0:
        return None
    return x0, y0, x0 + width, y0 + height


def validate_text_coordinates(
    clean_tree: CleanDesignTreeNode,
    flutter_mapper: FlutterCoordinateMapper | None,
    *,
    tolerance: int,
    image_width: int,
    image_height: int,
) -> TextCoordinateValidationResult:
    """Stage 1: compare TEXT node top-left corners before pixel diff."""
    if flutter_mapper is None:
        return TextCoordinateValidationResult(passed=True)

    design_w, design_h = _design_canvas_size(clean_tree)
    failures: list[TextCoordinateFailure] = []
    tol = float(tolerance)

    for node in iter_text_nodes(clean_tree):
        figma_rect = figma_text_box(
            node,
            design_width=design_w,
            design_height=design_h,
            image_width=image_width,
            image_height=image_height,
        )
        if figma_rect is None:
            continue
        figma_left = float(figma_rect[0])
        figma_top = float(figma_rect[1])
        flutter_bounds = flutter_mapper.rect_for_node_id(node.id)
        if flutter_bounds is None:
            continue
        flutter_left, flutter_top, _, _ = flutter_bounds
        delta_x = abs(figma_left - flutter_left)
        delta_y = abs(figma_top - flutter_top)
        if delta_x > tol or delta_y > tol:
            failures.append(
                TextCoordinateFailure(
                    node_id=node.id,
                    expected_left=figma_left,
                    expected_top=figma_top,
                    actual_left=flutter_left,
                    actual_top=flutter_top,
                    delta_x=delta_x,
                    delta_y=delta_y,
                )
            )

    return TextCoordinateValidationResult(
        passed=not failures,
        failures=tuple(failures),
    )
