"""Stateful interactive controls for deterministic layout."""

from __future__ import annotations

from figma_flutter_agent.generator.layout.choice_chip_row import (
    circular_option_chip_row_stateful_helpers,
    layout_fact_circular_option_chip_row_host,
)
from figma_flutter_agent.generator.layout.interactive_time import (
    extract_wheel_picker_columns,
    render_time_wheel_picker_stack,
    time_wheel_picker_stateful_helpers,
)
from figma_flutter_agent.generator.layout.interactive_toggle import (
    render_stateful_toggle_checkbox,
    toggle_checkbox_stateful_helpers,
)
from figma_flutter_agent.generator.layout.interactive_weekday import (
    render_weekday_chip_row,
    weekday_chip_row_stateful_helpers,
)
from figma_flutter_agent.parser.interaction import (
    layout_fact_checkbox_control,
    layout_fact_compact_chip_row,
    layout_fact_wheel_time_picker_stack,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode

__all__ = [
    "extract_wheel_picker_columns",
    "interactive_layout_helpers",
    "layout_interactive_helpers_needed",
    "render_stateful_toggle_checkbox",
    "render_time_wheel_picker_stack",
    "render_weekday_chip_row",
    "time_wheel_picker_stateful_helpers",
    "toggle_checkbox_stateful_helpers",
    "weekday_chip_row_stateful_helpers",
]


def _collect_extracted_materialization_root_ids(tree: CleanDesignTreeNode) -> frozenset[str]:
    """Return clean-tree node ids materialized as extracted widget files."""

    roots: set[str] = set()

    def walk(node: CleanDesignTreeNode) -> None:
        if node.extracted_widget_ref:
            roots.add(node.id)
        for child in node.children:
            walk(child)

    walk(tree)
    return frozenset(roots)


def _wheel_layout_helpers_suppressed_for_node(node: CleanDesignTreeNode) -> bool:
    """Return True when this wheel host delegates helpers to an extracted widget file."""
    from figma_flutter_agent.parser.interaction import must_inline_extracted_widget_host

    if not layout_fact_wheel_time_picker_stack(node):
        return False
    ref = (node.extracted_widget_ref or "").strip()
    if not ref:
        return False
    return not must_inline_extracted_widget_host(node)


def _is_deepest_wheel_host(node: CleanDesignTreeNode) -> bool:
    """Return True when this node is the innermost wheel-picker host in its branch."""
    if not layout_fact_wheel_time_picker_stack(node):
        return False
    return not any(layout_fact_wheel_time_picker_stack(child) for child in node.children)


def _delegated_extracted_subtree_ids(tree: CleanDesignTreeNode) -> frozenset[str]:
    """Return node ids under extracted-widget delegation hosts (not inlined)."""
    from figma_flutter_agent.parser.interaction import must_inline_extracted_widget_host

    blocked: set[str] = set()

    def walk(node: CleanDesignTreeNode, *, under_delegation: bool) -> None:
        if under_delegation:
            blocked.add(node.id)
        delegates = bool(
            (node.extracted_widget_ref or "").strip()
            and not must_inline_extracted_widget_host(node)
        )
        for child in node.children:
            walk(child, under_delegation=under_delegation or delegates)

    walk(tree, under_delegation=False)
    return frozenset(blocked)


def _interactive_helper_omitted_ids(
    tree: CleanDesignTreeNode,
    *,
    skip_helper_node_ids: frozenset[str] | None = None,
) -> frozenset[str]:
    """Return node ids that must not drive layout helper class emission."""
    return (skip_helper_node_ids or frozenset()) | _delegated_extracted_subtree_ids(tree)


def layout_interactive_helpers_needed(
    tree: CleanDesignTreeNode,
    *,
    skip_helper_node_ids: frozenset[str] | None = None,
) -> bool:
    """Return True when generated layout needs interactive helper widgets."""
    omitted = _interactive_helper_omitted_ids(tree, skip_helper_node_ids=skip_helper_node_ids)

    def walk(node: CleanDesignTreeNode) -> bool:
        if node.id not in omitted:
            if layout_fact_compact_chip_row(node):
                return True
            if layout_fact_circular_option_chip_row_host(node):
                return True
            if _is_deepest_wheel_host(node) and not _wheel_layout_helpers_suppressed_for_node(node):
                return True
            if layout_fact_checkbox_control(node):
                return True
        return any(walk(child) for child in node.children)

    return walk(tree)


def interactive_layout_helpers(
    tree: CleanDesignTreeNode,
    *,
    skip_helper_node_ids: frozenset[str] | None = None,
) -> str:
    """Compose all Dart helper classes required by ``tree``."""
    omitted = _interactive_helper_omitted_ids(tree, skip_helper_node_ids=skip_helper_node_ids)
    weekday_node_id: str | None = None
    circular_chip_row_id: str | None = None
    wheel_node_id: str | None = None
    needs_toggle_checkbox = False

    def walk(node: CleanDesignTreeNode) -> None:
        nonlocal weekday_node_id, circular_chip_row_id, wheel_node_id, needs_toggle_checkbox
        if weekday_node_id is None and layout_fact_compact_chip_row(node):
            if node.id not in omitted:
                weekday_node_id = node.id
        if circular_chip_row_id is None and layout_fact_circular_option_chip_row_host(node):
            if node.id not in omitted:
                circular_chip_row_id = node.id
        if wheel_node_id is None and _is_deepest_wheel_host(node):
            if node.id not in omitted and not _wheel_layout_helpers_suppressed_for_node(node):
                wheel_node_id = node.id
        if layout_fact_checkbox_control(node):
            needs_toggle_checkbox = True
        for child in node.children:
            walk(child)

    walk(tree)
    blocks: list[str] = []
    if weekday_node_id is not None:
        blocks.append(weekday_chip_row_stateful_helpers(weekday_node_id))
    if circular_chip_row_id is not None:
        blocks.append(circular_option_chip_row_stateful_helpers(circular_chip_row_id))
    if wheel_node_id is not None:
        blocks.append(time_wheel_picker_stateful_helpers(wheel_node_id))
    if needs_toggle_checkbox:
        blocks.append(toggle_checkbox_stateful_helpers())
    return "\n".join(blocks)
