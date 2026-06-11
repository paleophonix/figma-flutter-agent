"""Breakpoint-driven column/grid reflow helpers (spec §7.3)."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

from figma_flutter_agent.generator.artboard import (
    is_artboard_bounded_layout_width,
    is_mobile_artboard_width,
)
from figma_flutter_agent.parser.numeric_rounding import format_geometry_literal
from figma_flutter_agent.schemas import NodeType, SizingMode, StackPlacement


@dataclass(frozen=True)
class ResponsiveEmitContext:
    """Thread-local responsive emit flags for layout widget codegen."""

    enabled: bool = False
    design_artboard_width: float | None = None


_responsive_emit_ctx: ContextVar[ResponsiveEmitContext] = ContextVar(
    "responsive_emit_ctx",
    default=ResponsiveEmitContext(),
)


@contextmanager
def responsive_emit_context(
    *,
    enabled: bool,
    design_artboard_width: float | None,
):
    """Scope responsive width-stretch rules for nested layout emit."""
    token = _responsive_emit_ctx.set(
        ResponsiveEmitContext(
            enabled=enabled,
            design_artboard_width=design_artboard_width,
        )
    )
    try:
        yield
    finally:
        _responsive_emit_ctx.reset(token)


def current_responsive_emit() -> ResponsiveEmitContext:
    """Return the active responsive emit context."""
    return _responsive_emit_ctx.get()


_CONTENT_BAND_PADDING_ALLOWANCE = 48.0


def is_responsive_content_band_width(
    node_width: float | None,
    design_artboard_width: float | None,
) -> bool:
    """Return True when a width matches the padded content band inside a phone frame."""
    if node_width is None or design_artboard_width is None:
        return False
    if node_width <= 0 or design_artboard_width <= 0:
        return False
    if float(node_width) >= float(design_artboard_width) - _CONTENT_BAND_PADDING_ALLOWANCE:
        return True
    if float(node_width) >= float(design_artboard_width) * 0.8:
        return True
    # Chip rows and padded bands (~285px inside a 390px frame) must stretch in live hosts.
    return float(node_width) >= float(design_artboard_width) * 0.72


_CONTENT_BAND_MIN_WIDTH_RATIO = 0.75


def is_responsive_content_band_min_width(
    node_width: float | None,
    design_artboard_width: float | None,
) -> bool:
    """Return True when a Figma ``minWidth`` would block narrow-host shrink (horizontal scroll)."""
    if node_width is None or design_artboard_width is None:
        return False
    if node_width <= 0 or design_artboard_width <= 0:
        return False
    inner_band = float(design_artboard_width) - _CONTENT_BAND_PADDING_ALLOWANCE
    return float(node_width) >= inner_band * _CONTENT_BAND_MIN_WIDTH_RATIO


def responsive_emit_width(node_width: float | None) -> float | None:
    """Drop artboard-width caps during responsive emit; keep smaller fixed frames."""
    ctx = _responsive_emit_ctx.get()
    if not ctx.enabled or not is_mobile_artboard_width(ctx.design_artboard_width):
        return node_width
    if is_artboard_bounded_layout_width(node_width, ctx.design_artboard_width):
        return None
    if is_responsive_content_band_width(node_width, ctx.design_artboard_width):
        return None
    if is_responsive_content_band_min_width(node_width, ctx.design_artboard_width):
        return None
    return node_width


def responsive_host_width_literal(
    node_width: float | None,
    *,
    width_mode: SizingMode | None = None,
) -> str:
    """Return a Dart width literal for flex/stack hosts on wide viewports.

    Phone artboard frames keep Figma-fixed widths on-device but must stretch to
    ``double.infinity`` when ``responsive_enabled`` hosts them above 480px.
    """
    ctx = _responsive_emit_ctx.get()
    if ctx.enabled and is_mobile_artboard_width(ctx.design_artboard_width):
        if width_mode == SizingMode.FILL:
            return "double.infinity"
        if node_width is None or node_width <= 0:
            return "double.infinity"
        if is_artboard_bounded_layout_width(node_width, ctx.design_artboard_width):
            return "double.infinity"
        if is_responsive_content_band_width(node_width, ctx.design_artboard_width):
            return "double.infinity"
    if node_width is not None and node_width > 0:
        return format_geometry_literal(node_width)
    return "double.infinity"


def should_stretch_artboard_positioned_horizontal(
    placement: StackPlacement | None,
    width: float | None,
) -> bool:
    """Return True when a top-level positioned layer should span the live viewport."""
    ctx = _responsive_emit_ctx.get()
    if not ctx.enabled or not is_mobile_artboard_width(ctx.design_artboard_width):
        return False
    if placement is None or width is None or width <= 0:
        return False
    if not (
        is_artboard_bounded_layout_width(width, ctx.design_artboard_width)
        or is_responsive_content_band_width(width, ctx.design_artboard_width)
    ):
        return False
    left = placement.left if placement.left is not None else 0.0
    return float(left) <= 1.5


def should_stretch_bottom_positioned_horizontal(placement: StackPlacement) -> bool:
    """Return True when bottom-anchored chrome should span the host width."""
    ctx = _responsive_emit_ctx.get()
    if not ctx.enabled or not is_mobile_artboard_width(ctx.design_artboard_width):
        return False
    if placement.width is None or ctx.design_artboard_width is None:
        return False
    if not is_artboard_bounded_layout_width(
        placement.width,
        ctx.design_artboard_width,
    ):
        return False
    left = placement.left if placement.left is not None else 0.0
    if left > 1.5:
        return False
    if placement.vertical != "BOTTOM" and placement.bottom is None:
        return False
    return placement.horizontal in {"LEFT", "LEFT_RIGHT", "SCALE", "CENTER"}


def stretch_positioned_fields_horizontal(fields: list[str]) -> None:
    """Replace artboard-width ``Positioned`` pins with ``left``/``right`` stretch."""
    fields[:] = [field for field in fields if not field.startswith("width:")]
    has_left = any(field.startswith("left:") for field in fields)
    has_right = any(field.startswith("right:") for field in fields)
    if not has_left:
        fields.insert(0, "left: 0.0")
    else:
        fields[:] = [
            "left: 0.0" if field.startswith("left:") else field for field in fields
        ]
    if not has_right:
        fields.append("right: 0.0")

_WIDE_COLUMN_REFLOW = "AppBreakpoints.isWideLayout(width)"
_SIDE_NAV_LAYOUT = "AppBreakpoints.isDesktop(width) || AppBreakpoints.isTablet(width)"
# Match ``AppBreakpoints.mobileSmallMax``: Figma frames at or below this width are
# mobile-only designs and must not reflow when hosted in a wide web viewport.
_MOBILE_ONLY_ARTBOARD_MAX_WIDTH = 480.0


def wide_column_reflow_enabled(design_artboard_width: float | None) -> bool:
    """Return True when column→row reflow may activate above the mobile-small band.

    Phone-sized Figma frames (≤480px) are authored for a single column; emitting
    ``isWideLayout`` branches capped to the artboard width is dead code and bloats
    layout files without changing runtime (spec §7.3 / §9).
    """
    if design_artboard_width is None:
        return True
    return design_artboard_width > _MOBILE_ONLY_ARTBOARD_MAX_WIDTH


def responsive_layout_width_assignment(design_artboard_width: float | None) -> str:
    """Assign ``width`` for breakpoint checks inside ``LayoutBuilder``.

    Args:
        design_artboard_width: Root Figma frame width when known.

    Returns:
        A Dart ``final width = …;`` statement.
    """
    _ = design_artboard_width
    return "final width = constraints.maxWidth;"


def child_is_bottom_nav(widget: str) -> bool:
    """Return True when a child widget expression is the generated adaptive nav chrome."""
    return "_LayoutChromeNav(" in widget or "_LayoutBottomNav(" in widget


def should_responsive_reflow(child_widgets: list[str]) -> bool:
    """Return True when column children should reflow to Row on wide screens."""
    if len(child_widgets) < 2 or len(child_widgets) > 4:
        return False
    cluster_refs = sum(
        1
        for widget in child_widgets
        if widget.strip().startswith("const ") and "Widget()" in widget
    )
    return cluster_refs < len(child_widgets)


def should_apply_responsive_column_reflow(
    *,
    responsive_enabled: bool,
    scroll_axis: str,
    is_layout_root: bool,
    parent_type: NodeType | None,
    child_widgets: list[str],
    contains_form_control: bool = False,
    design_artboard_width: float | None = None,
) -> bool:
    """Return True when a Column should reflow to Row on mobile-large+ widths."""
    if not responsive_enabled or scroll_axis != "none":
        return False
    has_bottom_nav = bool(child_widgets) and child_is_bottom_nav(child_widgets[-1])
    if not has_bottom_nav and not wide_column_reflow_enabled(design_artboard_width):
        return False
    if contains_form_control:
        return False
    if not has_bottom_nav and not should_responsive_reflow(child_widgets):
        return False
    return is_layout_root or parent_type == NodeType.COLUMN


def _wrap_main_and_nav_chrome(
    *,
    main_axis: str,
    cross_axis: str,
    main_body: str,
    nav_widget: str,
    design_artboard_width: float | None = None,
) -> str:
    """Place main content and nav as bottom bar (mobile) or side rail (tablet/desktop)."""
    width_assign = responsive_layout_width_assignment(design_artboard_width)
    mobile_column = f"Column(children: [Expanded(child: {main_body}), {nav_widget}])"
    return (
        f"LayoutBuilder("
        f"builder: (context, constraints) {{"
        f"{width_assign}"
        f"if ({_SIDE_NAV_LAYOUT}) {{"
        f"return Row("
        f"crossAxisAlignment: CrossAxisAlignment.stretch, "
        f"children: ["
        f"{nav_widget}, "
        f"Expanded(child: {main_body})"
        f"]"
        f");"
        f"}}"
        f"return {mobile_column};"
        f"}})"
    )


def wrap_responsive_root_column(
    *,
    main_axis: str,
    cross_axis: str,
    child_widgets: list[str],
    design_artboard_width: float | None = None,
    spacing_field: str = "",
) -> str:
    """Reflow a Column to Row on mobile-large, tablet, and desktop (spec §7.3)."""
    width_assign = responsive_layout_width_assignment(design_artboard_width)
    nav_widget: str | None = None
    main_widgets = child_widgets
    if child_widgets and child_is_bottom_nav(child_widgets[-1]):
        nav_widget = child_widgets[-1]
        main_widgets = child_widgets[:-1]

    if nav_widget is not None:
        if should_responsive_reflow(main_widgets) and len(main_widgets) >= 2:
            row_children = ", ".join(f"Expanded(child: {widget})" for widget in main_widgets)
            main_body = (
                f"Row(crossAxisAlignment: CrossAxisAlignment.start, children: [{row_children}])"
            )
        else:
            body = ", ".join(main_widgets) or "const SizedBox.shrink()"
            main_body = (
                f"Column(mainAxisAlignment: {main_axis}, crossAxisAlignment: {cross_axis}, "
                f"{spacing_field}children: [{body}])"
            )
        return _wrap_main_and_nav_chrome(
            main_axis=main_axis,
            cross_axis=cross_axis,
            main_body=main_body,
            nav_widget=nav_widget,
            design_artboard_width=design_artboard_width,
        )

    column_body = ", ".join(child_widgets) or "const SizedBox.shrink()"
    mobile_small_column = (
        f"Column(mainAxisAlignment: {main_axis}, crossAxisAlignment: {cross_axis}, "
        f"{spacing_field}children: [{column_body}])"
    )
    if not wide_column_reflow_enabled(design_artboard_width):
        return mobile_small_column

    if not should_responsive_reflow(child_widgets):
        return mobile_small_column

    if len(main_widgets) < 2:
        return mobile_small_column

    row_children = ", ".join(f"Expanded(child: {widget})" for widget in main_widgets)
    wide_row = f"Row(crossAxisAlignment: CrossAxisAlignment.start, children: [{row_children}])"
    return (
        f"LayoutBuilder("
        f"builder: (context, constraints) {{"
        f"{width_assign}"
        f"if ({_WIDE_COLUMN_REFLOW}) {{"
        f"return {wide_row};"
        f"}}"
        f"return {mobile_small_column};"
        f"}})"
    )

