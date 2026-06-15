"""Cupertino wrappers for deterministic layout and screen shells."""

from __future__ import annotations

from figma_flutter_agent.generator.custom_code_zones import (
    custom_code_zone_id,
    inline_custom_code_comment,
)

_TEXT_SCALER_LINE = "    final textScaler = MediaQuery.textScalerOf(context);\n"


def _on_tap_handler(node_id: str, role: str) -> str:
    zone = custom_code_zone_id(node_id, role)
    comment = inline_custom_code_comment(zone)
    return f"onTap: () {{ {comment} }}, "


def _on_pressed_handler(node_id: str, role: str) -> str:
    zone = custom_code_zone_id(node_id, role)
    comment = inline_custom_code_comment(zone)
    return f"onPressed: () {{ {comment} }}, "


def is_cupertino(theme_variant: str) -> bool:
    return theme_variant == "cupertino"


def wrap_layout_root(
    widget: str,
    *,
    theme_variant: str,
    background_color: str | None,
) -> str:
    if is_cupertino(theme_variant):
        bg = (
            f"Color({background_color})" if background_color else "CupertinoColors.systemBackground"
        )
        return f"CupertinoPageScaffold(backgroundColor: {bg}, child: SafeArea(child: {widget}))"
    material_color = f"Color({background_color})" if background_color else "Colors.transparent"
    return f"Material(color: {material_color}, child: {widget})"


def wrap_button_stack(
    stack_widget: str,
    *,
    theme_variant: str,
    border_radius: float | None,
    ink_fill_color: str | None = None,
    ink_gradient: str | None = None,
    ink_border: str | None = None,
    ink_box_shadows: list[str] | None = None,
    ink_inner_overlays: list[str] | None = None,
    node_id: str,
    tap_role: str = "button-action",
) -> str:
    on_tap = _on_tap_handler(node_id, tap_role)
    if is_cupertino(theme_variant):
        gesture = (
            f"GestureDetector({on_tap}behavior: HitTestBehavior.opaque, child: {stack_widget})"
        )
        if border_radius is None:
            return gesture
        return f"ClipRRect(borderRadius: BorderRadius.circular({border_radius}), child: {gesture})"
    custom_border = (
        f"customBorder: RoundedRectangleBorder(borderRadius: BorderRadius.circular({border_radius})), "
        if border_radius is not None
        else ""
    )
    if ink_gradient is not None or ink_fill_color is not None:
        decoration_fields: list[str] = []
        if ink_gradient is not None:
            decoration_fields.append(f"gradient: {ink_gradient}")
        elif ink_fill_color is not None:
            decoration_fields.append(f"color: {ink_fill_color}")
        if border_radius is not None:
            decoration_fields.append(f"borderRadius: BorderRadius.circular({border_radius})")
        if ink_border is not None:
            decoration_fields.append(f"border: {ink_border}")
        if ink_box_shadows:
            decoration_fields.append(f"boxShadow: [{', '.join(ink_box_shadows)}]")
        decoration = f"BoxDecoration({', '.join(decoration_fields)})"
        # Extent comes from outer ``SizedBox`` in ``_wrap_button_stack`` — never
        # ``SizedBox.expand`` here (Row/Flexible gives unbounded cross-axis height).
        ink_child = stack_widget
        if ink_inner_overlays:
            from figma_flutter_agent.generator.layout.style.decoration import (
                wrap_with_inner_shadow_overlays,
            )

            radius_expr = (
                f"BorderRadius.circular({border_radius})" if border_radius is not None else None
            )
            ink_child = wrap_with_inner_shadow_overlays(
                stack_widget,
                ink_inner_overlays,
                border_radius_expr=radius_expr,
            )
        return (
            "Material("
            "elevation: 0, "
            "color: Colors.transparent, "
            f"child: Ink("
            f"decoration: {decoration}, "
            "child: InkWell("
            "splashColor: Color(0x1A000000), "
            "highlightColor: Color(0x0D000000), "
            f"{on_tap}"
            f"{custom_border}"
            f"child: {ink_child}"
            ")"
            ")"
            ")"
        )
    if border_radius is None:
        return (
            "Material("
            "elevation: 0, "
            "color: Colors.transparent, "
            "child: InkWell("
            "splashColor: Color(0x1A000000), "
            "highlightColor: Color(0x0D000000), "
            f"{on_tap}"
            f"child: {stack_widget}"
            ")"
            ")"
        )
    return (
        "Material("
        "elevation: 0, "
        "color: Colors.transparent, "
        f"borderRadius: BorderRadius.circular({border_radius}), "
        "clipBehavior: Clip.antiAlias, "
        "child: InkWell("
        "splashColor: Color(0x1A000000), "
        "highlightColor: Color(0x0D000000), "
        f"{on_tap}"
        f"borderRadius: BorderRadius.circular({border_radius}), "
        f"child: {stack_widget}"
        ")"
        ")"
    )


def wrap_circular_button_stack(
    stack_widget: str,
    *,
    theme_variant: str,
    node_id: str,
    tap_role: str = "button-action",
) -> str:
    """Circular Material ripple for round play/skip/icon controls without a pill surface."""
    on_tap = _on_tap_handler(node_id, tap_role)
    if is_cupertino(theme_variant):
        return f"GestureDetector({on_tap}behavior: HitTestBehavior.opaque, child: {stack_widget})"
    return (
        "Material("
        "elevation: 0, "
        "color: Colors.transparent, "
        "shape: const CircleBorder(), "
        "clipBehavior: Clip.antiAlias, "
        "child: InkWell("
        "customBorder: const CircleBorder(), "
        "splashColor: Color(0x1A000000), "
        "highlightColor: Color(0x0D000000), "
        f"{on_tap}"
        f"child: {stack_widget}"
        ")"
        ")"
    )


def wrap_back_nav_stack(stack_widget: str, *, theme_variant: str, node_id: str) -> str:
    on_tap = _on_tap_handler(node_id, "back-nav")
    if is_cupertino(theme_variant):
        return f"GestureDetector({on_tap}behavior: HitTestBehavior.opaque, child: {stack_widget})"
    return (
        "Material("
        "elevation: 0, "
        "color: Colors.transparent, "
        "shape: const CircleBorder(), "
        "clipBehavior: Clip.antiAlias, "
        "child: InkWell("
        "customBorder: const CircleBorder(), "
        "splashColor: Color(0x1A000000), "
        "highlightColor: Color(0x0D000000), "
        f"{on_tap}"
        f"child: {stack_widget}"
        ")"
        ")"
    )


def wrap_button_children_stack(
    body: str,
    label: str,
    *,
    theme_variant: str,
    border_radius: float | None = None,
    node_id: str,
) -> str:
    stack = f"Stack(clipBehavior: Clip.none, children: [{body}])"
    wrapped = wrap_button_stack(
        stack,
        theme_variant=theme_variant,
        border_radius=border_radius,
        node_id=node_id,
    )
    return f"Semantics(label: '{label}', child: {wrapped})"


def wrap_scroll_viewport(viewport: str, *, theme_variant: str) -> str:
    if is_cupertino(theme_variant):
        return f"Center(child: {viewport})"
    return f"Center(child: Material(color: Colors.transparent, child: {viewport}))"


def screen_shell_dart(
    *,
    body: str,
    theme_variant: str,
    use_scaffold: bool,
    title: str,
    needs_scaler_preamble: bool,
) -> tuple[str, str]:
    """Return ``(root_widget, build_method_preamble)`` for a screen class."""
    if not use_scaffold:
        preamble = _TEXT_SCALER_LINE if needs_scaler_preamble else ""
        return body, preamble
    escaped_title = title.replace("'", "\\'")
    if is_cupertino(theme_variant):
        root = (
            "CupertinoPageScaffold("
            f"navigationBar: CupertinoNavigationBar(middle: Text('{escaped_title}')), "
            f"child: SafeArea(child: {body}),"
            ")"
        )
        return root, _TEXT_SCALER_LINE
    root = (
        "Scaffold("
        f"appBar: AppBar(title: Text('{escaped_title}', textScaler: textScaler)), "
        f"body: {body},"
        ")"
    )
    return root, _TEXT_SCALER_LINE
