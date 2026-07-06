"""Flex sizing, wrap helpers, and Positioned field emitters."""

from __future__ import annotations

from collections.abc import Callable

from figma_flutter_agent.generator.layout.common import (
    normalize_box_constraints,
)
from figma_flutter_agent.parser.numeric_rounding import format_geometry_literal
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeType,
    SizingMode,
    WrapKind,
)

_SKIP_NUMERAL_DOWN_NUDGE = 2.5
_LIST_TILE_TRAIL_MAX_WIDTH = 32.0
_LIST_TILE_TRAILING_CHEVRON = (
    "Icon(Icons.chevron_right_rounded, color: Theme.of(context).colorScheme.onSurfaceVariant)"
)


def _flex_parent_data_wrapper(widget: str) -> bool:
    """Return True when ``widget`` is already an ``Expanded`` / ``Flexible`` wrapper."""
    trimmed = widget.lstrip()
    return trimmed.startswith(("Expanded(", "Flexible(", "const Expanded(", "const Flexible("))


def _extract_balanced_prefix_child(source: str, child_start: int) -> str | None:
    """Return the balanced child expression starting at ``child_start``."""
    depth = 0
    for index in range(child_start, len(source)):
        char = source[index]
        if char == "(":
            depth += 1
        elif char == ")":
            if depth == 0:
                return source[child_start:index]
            depth -= 1
    return None


def _unwrap_flex_parent_data_wrapper(widget: str) -> tuple[str, str] | None:
    """Return ``(wrapper_prefix, inner)`` for a top-level Expanded/Flexible wrapper."""
    trimmed = widget.lstrip()
    for marker in (
        "Expanded(child: ",
        "Flexible(fit: FlexFit.loose, flex: 0, child: ",
        "Flexible(fit: FlexFit.loose, child: ",
        "Flexible(child: ",
        "const Expanded(child: ",
        "const Flexible(fit: FlexFit.loose, flex: 0, child: ",
        "const Flexible(fit: FlexFit.loose, child: ",
        "const Flexible(child: ",
    ):
        if trimmed.startswith(marker):
            inner = _extract_balanced_prefix_child(trimmed, len(marker))
            if inner is not None:
                return marker, inner
    return None


def _hoist_flex_parent_data(wrapper: Callable[[str], str], widget: str) -> str:
    """Apply ``wrapper`` inside ``Expanded``/``Flexible`` when already present."""
    from figma_flutter_agent.generator.layout.flex_policy import hoist_flex_parent_data

    return hoist_flex_parent_data(wrapper, widget)


def _wrap_center_preserving_flex_parent_data(widget: str) -> str:
    """Center a flex child without nesting ``Expanded``/``Flexible`` under ``Center``."""
    return _hoist_flex_parent_data(lambda inner: f"Center(child: {inner})", widget)


def _wrap_sizing(
    node: CleanDesignTreeNode,
    widget: str,
    *,
    parent_type: NodeType | None,
    parent_node: CleanDesignTreeNode | None = None,
) -> str:
    from figma_flutter_agent.generator.layout.flex_policy import (
        apply_flex_wrap_to_widget,
    )

    slot = node.layout_slot
    slot_handles_flex = (
        slot is not None
        and parent_type in {NodeType.ROW, NodeType.COLUMN}
        and (WrapKind.EXPANDED in slot.wraps or WrapKind.FLEXIBLE_LOOSE in slot.wraps)
    )
    if slot_handles_flex:
        wrapped = widget
    else:
        wrapped = apply_flex_wrap_to_widget(
            widget,
            parent_type=parent_type,
            node=node,
            parent_node=parent_node,
        )
    sizing = node.sizing
    from figma_flutter_agent.generator.layout.responsive import responsive_emit_width

    min_width, max_width = normalize_box_constraints(
        responsive_emit_width(sizing.min_width),
        sizing.max_width,
    )
    if (
        min_width is not None
        and sizing.width is not None
        and sizing.width_mode in {SizingMode.FIXED, SizingMode.HUG}
        and float(sizing.width) > 0
        and float(min_width) > float(sizing.width)
    ):
        min_width = float(sizing.width)
    min_height, max_height = normalize_box_constraints(
        sizing.min_height,
        sizing.max_height,
    )
    if node.type == NodeType.INPUT:
        from figma_flutter_agent.parser.interaction import input_external_label_node

        if input_external_label_node(node) is not None:
            min_height = None
            max_height = None
    constraint_parts: list[str] = []
    if min_width is not None:
        constraint_parts.append(f"minWidth: {format_geometry_literal(min_width)}")
    if max_width is not None:
        constraint_parts.append(f"maxWidth: {format_geometry_literal(max_width)}")
    if min_height is not None:
        constraint_parts.append(f"minHeight: {format_geometry_literal(min_height)}")
    if max_height is not None:
        constraint_parts.append(f"maxHeight: {format_geometry_literal(max_height)}")
    if constraint_parts:
        wrapped = (
            f"ConstrainedBox(constraints: BoxConstraints({', '.join(constraint_parts)}), "
            f"child: {wrapped})"
        )
    # ROW cross-axis height pins run in ``post_flex_layout_slot_extents`` after
    # ``Expanded``/``Flexible`` wrappers — binding here duplicates ``OverflowBox``
    # layers and can emit ``maxHeight: double.infinity`` inside ``Expanded``.
    from figma_flutter_agent.generator.layout.flex_policy.wrap import repair_flex_parent_data_order

    return repair_flex_parent_data_order(wrapped)


def flex_children_body(
    node: CleanDesignTreeNode,
    child_widgets: list[str],
    *,
    axis: str,
    explicit_gap_cap: float | None = None,
) -> str:
    """Join flex child widgets, inserting explicit ``SizedBox`` gaps when requested."""
    if not child_widgets:
        return "const SizedBox.shrink()"
    if explicit_gap_cap is not None and node.spacing > 0 and len(child_widgets) >= 2:
        size_kw = "width" if axis == "horizontal" else "height"
        gap = format_geometry_literal(min(float(node.spacing), float(explicit_gap_cap)))
        parts: list[str] = []
        for index, widget in enumerate(child_widgets):
            parts.append(widget)
            if index < len(child_widgets) - 1:
                parts.append(f"SizedBox({size_kw}: {gap})")
        return ", ".join(parts)
    if node.flex_gap_mode != "explicit" or not node.flex_explicit_gaps:
        return ", ".join(child_widgets)
    size_kw = "width" if axis == "horizontal" else "height"
    parts: list[str] = []
    for index, widget in enumerate(child_widgets):
        parts.append(widget)
        if index < len(child_widgets) - 1:
            gap_index = min(index, len(node.flex_explicit_gaps) - 1)
            gap_value = node.flex_explicit_gaps[gap_index]
            gap = format_geometry_literal(gap_value)
            parts.append(f"SizedBox({size_kw}: {gap})")
    return ", ".join(parts)


def _flex_spacing_field(node: CleanDesignTreeNode) -> str:
    """Emit Flutter 3.27+ ``spacing`` on ``Row``/``Column`` when Figma gap is set."""
    if node.flex_gap_mode == "explicit":
        return ""
    if node.spacing == 0:
        return ""
    main = node.alignment.main or "start"
    if main in {"spaceBetween", "stretch"} and node.spacing > 0:
        return ""
    gap = format_geometry_literal(node.spacing)
    return f"spacing: {gap}, "


def _button_social_auth_icon_label_row_body(
    node: CleanDesignTreeNode, child_widgets: list[str]
) -> str:
    """Compose a centered icon + label ``Row`` for social auth button bodies."""
    parts: list[str] = []
    for child_node, widget in zip(node.children, child_widgets, strict=True):
        if child_node.type == NodeType.TEXT:
            parts.append(widget)
            continue
        width = child_node.sizing.width
        height = child_node.sizing.height
        if width is not None and height is not None and float(width) > 0 and float(height) > 0:
            widget = (
                f"SizedBox("
                f"width: {format_geometry_literal(width)}, "
                f"height: {format_geometry_literal(height)}, "
                f"child: {widget})"
            )
        parts.append(widget)
    spacing_field = _flex_spacing_field(node)
    return (
        "Row("
        "mainAxisAlignment: MainAxisAlignment.center, "
        "crossAxisAlignment: CrossAxisAlignment.center, "
        f"{spacing_field}"
        f"children: [{', '.join(parts)}]"
        ")"
    )


def _button_icon_label_inline_row_body(node: CleanDesignTreeNode, child_widgets: list[str]) -> str:
    """Compose a start-aligned icon + label ``Row`` for compact link affordances."""
    body = _button_social_auth_icon_label_row_body(node, child_widgets)
    return body.replace(
        "mainAxisAlignment: MainAxisAlignment.center, ",
        "mainAxisAlignment: MainAxisAlignment.start, ",
    )


def _button_painted_surface_overlay_body(
    node: CleanDesignTreeNode,
    child_widgets: list[str],
    *,
    emitted_pairs: list[tuple[CleanDesignTreeNode, str]] | None = None,
) -> str:
    """Compose a full-bleed painted surface with centered overlaid label text."""
    from figma_flutter_agent.generator.layout.widget_roots import strip_stack_parent_data_wrappers
    from figma_flutter_agent.parser.interaction.buttons import button_painted_overlay_surface
    from figma_flutter_agent.parser.interaction.input_fields import surface_covers_node

    pairs = emitted_pairs or list(zip(node.children, child_widgets, strict=False))
    ink_surface = button_painted_overlay_surface(node)
    label_pair = next(
        (
            (child, widget)
            for child, widget in pairs
            if child.type == NodeType.TEXT and (child.text or "").strip()
        ),
        None,
    )
    if ink_surface is not None:
        if label_pair is not None:
            label_widget = strip_stack_parent_data_wrappers(label_pair[1])
            return f"Center(child: {label_widget})"
        if len(child_widgets) == 1:
            single = strip_stack_parent_data_wrappers(child_widgets[0])
            return f"Center(child: {single})"
    if label_pair is None:
        return ", ".join(child_widgets)
    label_widget = strip_stack_parent_data_wrappers(label_pair[1])
    background_pair = next(
        (
            (child, widget)
            for child, widget in pairs
            if child.type != NodeType.TEXT and surface_covers_node(node, child)
        ),
        None,
    )
    if background_pair is None:
        return ", ".join(child_widgets)
    background_widget = strip_stack_parent_data_wrappers(background_pair[1])
    return (
        "Stack("
        "fit: StackFit.expand, "
        "clipBehavior: Clip.none, "
        f"children: [Positioned.fill(child: {background_widget}), "
        f"Center(child: {label_widget})]"
        ")"
    )


def _button_absolute_slot_stack_body(
    node: CleanDesignTreeNode,
    child_widgets: list[str],
    *,
    emitted_pairs: list[tuple[CleanDesignTreeNode, str]] | None = None,
) -> str:
    """Preserve absolutely positioned row chrome inside a tappable stack host."""
    from figma_flutter_agent.generator.layout.widgets.positioned import _positioned_fields

    pairs = emitted_pairs or list(zip(node.children, child_widgets, strict=False))
    parent_height = float(node.sizing.height or 0.0) or None
    parts: list[str] = []
    for child, widget in pairs:
        stripped = widget.strip()
        if stripped.startswith("Positioned("):
            parts.append(widget)
            continue
        placement = child.stack_placement
        if placement is None or (placement.left is None and placement.right is None):
            parts.append(widget)
            continue
        fields = _positioned_fields(placement, parent_height=parent_height)
        if not fields:
            parts.append(widget)
            continue
        parts.append(f"Positioned({', '.join(fields)}, child: {widget})")
    body = ", ".join(parts)
    return f"Stack(clipBehavior: Clip.none, fit: StackFit.expand, children: [{body}])"


def _button_list_tile_row_body(node: CleanDesignTreeNode, child_widgets: list[str]) -> str:
    """Compose a settings-style ``Row`` for auto-layout list tile buttons."""
    parts: list[str] = []
    for index, (child_node, widget) in enumerate(zip(node.children, child_widgets, strict=True)):
        if (
            index == len(node.children) - 1
            and len(node.children) >= 3
            and child_node.sizing.width is not None
            and float(child_node.sizing.width) <= _LIST_TILE_TRAIL_MAX_WIDTH
        ):
            widget = _LIST_TILE_TRAILING_CHEVRON
        if child_node.sizing.width_mode == SizingMode.FILL:
            parts.append(f"Expanded(child: {widget})")
        else:
            parts.append(widget)
    body = ", ".join(parts)
    return (
        "Row("
        "crossAxisAlignment: CrossAxisAlignment.center, "
        f"{_flex_spacing_field(node)}"
        f"children: [{body}]"
        ")"
    )
