"""Stateful interactive controls for deterministic layout."""

from __future__ import annotations

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
from figma_flutter_agent.generator.layout.choice_chip_row import (
    circular_option_chip_row_stateful_helpers,
    layout_fact_circular_option_chip_row_host,
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


def _wheel_helpers_suppressed_for_extracted_materialization(
    tree: CleanDesignTreeNode,
) -> bool:
    """Return True when wheel picker helpers belong only in an extracted widget file."""

    def subtree_has_wheel(node: CleanDesignTreeNode) -> bool:
        if layout_fact_wheel_time_picker_stack(node):
            return True
        return any(subtree_has_wheel(child) for child in node.children)

    def walk(node: CleanDesignTreeNode) -> bool:
        if node.extracted_widget_ref and subtree_has_wheel(node):
            return True
        return any(walk(child) for child in node.children)

    return walk(tree)


def layout_interactive_helpers_needed(
    tree: CleanDesignTreeNode,
    *,
    skip_helper_node_ids: frozenset[str] | None = None,
    skip_wheel_helpers: bool = False,
) -> bool:
    """Return True when generated layout needs interactive helper widgets."""
    omitted = skip_helper_node_ids or frozenset()

    def walk(node: CleanDesignTreeNode) -> bool:
        if node.id not in omitted:
            if layout_fact_compact_chip_row(node):
                return True
            if layout_fact_circular_option_chip_row_host(node):
                return True
            if layout_fact_wheel_time_picker_stack(node) and not skip_wheel_helpers:
                return True
            if layout_fact_checkbox_control(node):
                return True
        return any(walk(child) for child in node.children)

    return walk(tree)


def interactive_layout_helpers(
    tree: CleanDesignTreeNode,
    *,
    skip_helper_node_ids: frozenset[str] | None = None,
    skip_wheel_helpers: bool = False,
) -> str:
    """Compose all Dart helper classes required by ``tree``."""
    omitted = skip_helper_node_ids or frozenset()
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
        if wheel_node_id is None and layout_fact_wheel_time_picker_stack(node):
            if node.id not in omitted and not skip_wheel_helpers:
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
