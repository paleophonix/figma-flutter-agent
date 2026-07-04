"""Layout facts for decomposed absolute painted field shells."""

from __future__ import annotations

from figma_flutter_agent.schemas import CleanDesignTreeNode, GeomRect, NodeType

_SINGLE_LINE_FIELD_MIN_WIDTH = 200.0
_SINGLE_LINE_FIELD_MAX_WIDTH = 480.0
_SINGLE_LINE_FIELD_MIN_HEIGHT = 36.0
_SINGLE_LINE_FIELD_MAX_HEIGHT = 56.0
_MULTILINE_FIELD_MIN_HEIGHT = 80.0
_MULTILINE_FIELD_MAX_HEIGHT = 280.0
_FIELD_VALUE_HORIZONTAL_INSET = 8.0
_CARD_SHELL_MIN_BORDER_RADIUS = 20.0


def layout_fact_painted_dashboard_card_shell(node: CleanDesignTreeNode) -> bool:
    """Return True for large-radius painted dashboard cards that are not form fields."""
    if node.type != NodeType.CONTAINER:
        return False
    if not node.style.background_color:
        return False
    radius = node.style.border_radius
    if radius is None or float(radius) < _CARD_SHELL_MIN_BORDER_RADIUS:
        return False
    width = node.sizing.width
    height = node.sizing.height
    if width is None or height is None:
        return False
    if float(width) < _SINGLE_LINE_FIELD_MIN_WIDTH:
        return False
    return float(height) >= _MULTILINE_FIELD_MIN_HEIGHT


def painted_dashboard_card_vertical_span(
    node: CleanDesignTreeNode,
) -> tuple[float, float] | None:
    """Return inclusive top/bottom span for a painted dashboard card shell."""
    return field_shell_vertical_span(node)


def _field_shell_layout_rect(node: CleanDesignTreeNode) -> GeomRect | None:
    """Return conserved layout rect for an absolute field shell when present."""
    frame = node.geometry_frame
    if frame is None or frame.layout_rect is None:
        return None
    rect = frame.layout_rect
    if rect.width is None or rect.height is None or rect.width <= 0 or rect.height <= 0:
        return None
    x = float(rect.x)
    y = float(rect.y)
    placement = node.stack_placement
    if placement is not None:
        if placement.left is not None:
            x = float(placement.left)
        if placement.top is not None:
            y = float(placement.top)
    return GeomRect(x=x, y=y, width=float(rect.width), height=float(rect.height))


def layout_fact_painted_multiline_field_shell(node: CleanDesignTreeNode) -> bool:
    """Return True for tall painted containers that host multiline entry."""
    if layout_fact_painted_dashboard_card_shell(node):
        return False
    if node.type != NodeType.CONTAINER:
        return False
    if not node.style.background_color:
        return False
    if node.stack_placement is None or node.stack_placement.top is None:
        return False
    width = node.sizing.width
    height = node.sizing.height
    if width is None or height is None:
        return False
    w = float(width)
    h = float(height)
    if w < _SINGLE_LINE_FIELD_MIN_WIDTH or w > _SINGLE_LINE_FIELD_MAX_WIDTH:
        return False
    return _MULTILINE_FIELD_MIN_HEIGHT <= h <= _MULTILINE_FIELD_MAX_HEIGHT


def layout_fact_painted_single_line_field_shell(node: CleanDesignTreeNode) -> bool:
    """Return True for compact painted containers that host single-line entry."""
    if layout_fact_painted_multiline_field_shell(node):
        return False
    if node.type != NodeType.CONTAINER:
        return False
    if not node.style.background_color:
        return False
    if node.stack_placement is None or node.stack_placement.top is None:
        return False
    width = node.sizing.width
    height = node.sizing.height
    if width is None or height is None:
        return False
    w = float(width)
    h = float(height)
    return (
        _SINGLE_LINE_FIELD_MIN_WIDTH <= w <= _SINGLE_LINE_FIELD_MAX_WIDTH
        and _SINGLE_LINE_FIELD_MIN_HEIGHT <= h <= _SINGLE_LINE_FIELD_MAX_HEIGHT
    )


def layout_fact_painted_field_shell_container(node: CleanDesignTreeNode) -> bool:
    """Return True for painted absolute containers that should emit interactive fields."""
    return layout_fact_painted_single_line_field_shell(
        node
    ) or layout_fact_painted_multiline_field_shell(node)


def field_shell_vertical_span(node: CleanDesignTreeNode) -> tuple[float, float] | None:
    """Return inclusive top/bottom span for a painted field shell."""
    rect = _field_shell_layout_rect(node)
    if rect is not None:
        return float(rect.y), float(rect.y) + float(rect.height)
    placement = node.stack_placement
    height = node.sizing.height
    if placement is None or placement.top is None or height is None:
        return None
    top = float(placement.top)
    return top, top + float(height)


def _text_layout_rect(
    node: CleanDesignTreeNode,
    *,
    host_height: float | None = None,
) -> GeomRect | None:
    frame = node.geometry_frame
    if frame is None or frame.layout_rect is None:
        return None
    rect = frame.layout_rect
    if rect.width is None or rect.height is None or rect.width <= 0 or rect.height <= 0:
        return None
    x = float(rect.x)
    y = float(rect.y)
    placement = node.stack_placement
    if placement is not None:
        if placement.left is not None:
            x = float(placement.left)
        if placement.top is not None:
            y = float(placement.top)
        elif placement.bottom is not None and host_height is not None:
            y = float(host_height) - float(placement.bottom) - float(rect.height)
    return GeomRect(x=x, y=y, width=float(rect.width), height=float(rect.height))


def find_field_shell_value_text(
    shell: CleanDesignTreeNode,
    siblings: list[CleanDesignTreeNode],
    *,
    host_height: float | None = None,
) -> CleanDesignTreeNode | None:
    """Resolve the in-shell value or placeholder text sibling for a field shell."""
    span = field_shell_vertical_span(shell)
    shell_rect = _field_shell_layout_rect(shell)
    if span is None or shell_rect is None:
        return None
    top, bottom = span
    shell_left = float(shell_rect.x)
    shell_right = shell_left + float(shell_rect.width)
    best: CleanDesignTreeNode | None = None
    best_score = -1.0
    for sibling in siblings:
        if sibling.id == shell.id or sibling.type != NodeType.TEXT:
            continue
        text = (sibling.text or "").strip()
        if not text:
            continue
        text_rect = _text_layout_rect(sibling, host_height=host_height)
        if text_rect is None:
            continue
        text_top = float(text_rect.y)
        if text_top < top - 2.0 or text_top > bottom - 2.0:
            continue
        text_left = float(text_rect.x)
        if text_left < shell_left + _FIELD_VALUE_HORIZONTAL_INSET:
            continue
        if text_left > shell_right + 4.0:
            continue
        score = float(text_rect.width or 0.0)
        if score > best_score:
            best = sibling
            best_score = score
    return best


def _resolve_field_shell_external_label(
    shell: CleanDesignTreeNode,
    siblings: list[CleanDesignTreeNode],
    *,
    host_height: float | None = None,
) -> tuple[CleanDesignTreeNode, float] | None:
    """Resolve external label text and the geometry gap down to the painted shell."""
    span = field_shell_vertical_span(shell)
    if span is None:
        return None
    shell_top, _ = span
    best: CleanDesignTreeNode | None = None
    best_gap = float("inf")
    for sibling in siblings:
        if sibling.id == shell.id or sibling.type != NodeType.TEXT:
            continue
        text = (sibling.text or "").strip()
        if not text:
            continue
        text_rect = _text_layout_rect(sibling, host_height=host_height)
        if text_rect is None:
            continue
        text_bottom = float(text_rect.y) + float(text_rect.height or 0.0)
        if text_bottom > shell_top + 2.0:
            continue
        gap = shell_top - text_bottom
        if gap < 0.0:
            continue
        if gap < best_gap:
            best = sibling
            best_gap = gap
    if best is None or best_gap == float("inf"):
        return None
    return best, best_gap


def find_field_shell_external_label(
    shell: CleanDesignTreeNode,
    siblings: list[CleanDesignTreeNode],
    *,
    host_height: float | None = None,
) -> CleanDesignTreeNode | None:
    """Resolve label text placed above a painted field shell (outside the shell span)."""
    resolved = _resolve_field_shell_external_label(
        shell,
        siblings,
        host_height=host_height,
    )
    if resolved is None:
        return None
    return resolved[0]


def field_shell_external_label_gap(
    shell: CleanDesignTreeNode,
    siblings: list[CleanDesignTreeNode],
    *,
    host_height: float | None = None,
) -> float | None:
    """Derive label-to-field spacing from absolute placements when present."""
    resolved = _resolve_field_shell_external_label(
        shell,
        siblings,
        host_height=host_height,
    )
    if resolved is None:
        return None
    gap = resolved[1]
    if gap <= 0.0:
        return None
    return gap


def layout_fact_labeled_absolute_field_stack(node: CleanDesignTreeNode) -> bool:
    """Return True when an absolute stack hosts an external label plus painted field."""
    if node.type != NodeType.STACK:
        return False
    shells = [
        child
        for child in node.children
        if layout_fact_painted_field_shell_container(child)
    ]
    if len(shells) != 1:
        return False
    shell = shells[0]
    host_height = node.sizing.height
    if find_field_shell_value_text(shell, node.children, host_height=host_height) is None:
        return False
    return (
        find_field_shell_external_label(shell, node.children, host_height=host_height) is not None
    )
