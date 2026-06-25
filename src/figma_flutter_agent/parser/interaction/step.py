"""Step and progress-indicator layout facts."""

from __future__ import annotations

from figma_flutter_agent.generator.variant.state import state_value
from figma_flutter_agent.parser.interaction.shared import _descendant_nodes
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

_DONE_STATES = frozenset({"done", "complete", "completed", "success"})


def _stack_has_success_component(node: CleanDesignTreeNode) -> bool:
    for item in _descendant_nodes(node, 4):
        name = (item.name or "").strip().lower()
        if name == "success":
            return True
        if item.variant is not None:
            component = (item.variant.component_name or "").strip().lower()
            if component == "success":
                return True
    return False


def layout_fact_step_indicator_glyph_stack(node: CleanDesignTreeNode) -> bool:
    """Compact circular step glyph (background + numeral or success), not media skip controls."""
    if node.type != NodeType.STACK:
        return False
    width = node.sizing.width
    height = node.sizing.height
    if width is None or height is None:
        return False
    if not (20.0 <= float(width) <= 32.0 and 20.0 <= float(height) <= 32.0):
        return False
    has_background = any(
        child.type in {NodeType.VECTOR, NodeType.CONTAINER, NodeType.STACK}
        and (
            child.vector_asset_key
            or child.style.background_color
            or child.children
        )
        for child in node.children
    )
    if not has_background:
        return False
    has_digit = any(
        child.type == NodeType.TEXT
        and (child.text or "").strip().isdigit()
        and len((child.text or "").strip()) <= 2
        for child in node.children
    )
    return has_digit or _stack_has_success_component(node)


def layout_fact_nav_stepper_row(node: CleanDesignTreeNode) -> bool:
    """Horizontal stepper host: multiple glyph+title columns in one row."""
    if node.type != NodeType.ROW or len(node.children) < 3:
        return False
    step_columns = sum(
        1 for child in node.children if layout_fact_step_indicator_title_column(child)
    )
    return step_columns >= 3


def layout_fact_step_indicator_title_column(parent_node: CleanDesignTreeNode) -> bool:
    """Column hosting a step glyph stack and a title label beneath it."""
    if parent_node.type != NodeType.COLUMN:
        return False
    has_glyph = any(
        layout_fact_step_indicator_glyph_stack(child) for child in parent_node.children
    )
    has_title = any(child.type == NodeType.TEXT for child in parent_node.children)
    return has_glyph and has_title


def layout_fact_step_indicator_completed(node: CleanDesignTreeNode) -> bool:
    """Return True when a step glyph stack is in a completed / done variant state."""
    if not layout_fact_step_indicator_glyph_stack(node):
        return False
    state = state_value(node)
    if state in _DONE_STATES:
        return True
    for item in _descendant_nodes(node, 3):
        if state_value(item) in _DONE_STATES:
            return True
    return _stack_has_success_component(node)


def layout_fact_success_check_glyph_host(node: CleanDesignTreeNode) -> bool:
    """Success/check component that must inline full glyph layers, not a raster stub."""
    name = (node.name or "").strip().lower()
    component = ""
    if node.variant is not None:
        component = (node.variant.component_name or "").strip().lower()
    if name != "success" and component != "success":
        return False
    if len(node.children) > 1:
        return True
    for item in _descendant_nodes(node, 4):
        if item.vector_asset_key:
            return True
        if item.type == NodeType.STACK and item.children:
            return True
    return False
