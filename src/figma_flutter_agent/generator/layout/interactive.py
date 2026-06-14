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
from figma_flutter_agent.parser.interaction import (
    is_compact_chip_row,
    looks_like_checkbox_control,
    looks_like_wheel_time_picker_stack,
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


def layout_interactive_helpers_needed(tree: CleanDesignTreeNode) -> bool:
    """Return True when generated layout needs interactive helper widgets."""

    def walk(node: CleanDesignTreeNode) -> bool:
        if is_compact_chip_row(node):
            return True
        if looks_like_wheel_time_picker_stack(node):
            return True
        if looks_like_checkbox_control(node):
            return True
        return any(walk(child) for child in node.children)

    return walk(tree)


def interactive_layout_helpers(tree: CleanDesignTreeNode) -> str:
    """Compose all Dart helper classes required by ``tree``."""
    weekday_node_id: str | None = None
    wheel_node_id: str | None = None
    needs_toggle_checkbox = False

    def walk(node: CleanDesignTreeNode) -> None:
        nonlocal weekday_node_id, wheel_node_id, needs_toggle_checkbox
        if weekday_node_id is None and is_compact_chip_row(node):
            weekday_node_id = node.id
        if wheel_node_id is None and looks_like_wheel_time_picker_stack(node):
            wheel_node_id = node.id
        if looks_like_checkbox_control(node):
            needs_toggle_checkbox = True
        for child in node.children:
            walk(child)

    walk(tree)
    blocks: list[str] = []
    if weekday_node_id is not None:
        blocks.append(weekday_chip_row_stateful_helpers(weekday_node_id))
    if wheel_node_id is not None:
        blocks.append(time_wheel_picker_stateful_helpers(wheel_node_id))
    if needs_toggle_checkbox:
        blocks.append(toggle_checkbox_stateful_helpers())
    return "\n".join(blocks)
