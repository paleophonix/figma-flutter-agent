"""Cupertino wrappers for deterministic layout and screen shells."""

from __future__ import annotations

_TEXT_SCALER_LINE = "    final textScaler = MediaQuery.textScalerOf(context);\n"


def is_cupertino(theme_variant: str) -> bool:
    return theme_variant == "cupertino"


def wrap_layout_root(
    widget: str,
    *,
    theme_variant: str,
    background_color: str | None,
) -> str:
    if is_cupertino(theme_variant):
        bg = f"Color({background_color})" if background_color else "CupertinoColors.systemBackground"
        return (
            f"CupertinoPageScaffold("
            f"backgroundColor: {bg}, "
            f"child: SafeArea(child: {widget})"
            f")"
        )
    material_color = f"Color({background_color})" if background_color else "Colors.transparent"
    return f"Material(color: {material_color}, child: {widget})"


def wrap_button_stack(
    stack_widget: str,
    *,
    theme_variant: str,
    border_radius: float | None,
    ink_fill_color: str | None = None,
    ink_border: str | None = None,
) -> str:
    if is_cupertino(theme_variant):
        gesture = (
            f"GestureDetector("
            f"onTap: () {{ /* <custom-code:button-action> */ }}, "
            f"behavior: HitTestBehavior.opaque, "
            f"child: {stack_widget}"
            f")"
        )
        if border_radius is None:
            return gesture
        return (
            f"ClipRRect("
            f"borderRadius: BorderRadius.circular({border_radius}), "
            f"child: {gesture}"
            f")"
        )
    custom_border = (
        f"customBorder: RoundedRectangleBorder(borderRadius: BorderRadius.circular({border_radius})), "
        if border_radius is not None
        else ""
    )
    if ink_fill_color is not None:
        decoration_fields = [f"color: {ink_fill_color}"]
        if border_radius is not None:
            decoration_fields.append(f"borderRadius: BorderRadius.circular({border_radius})")
        if ink_border is not None:
            decoration_fields.append(f"border: {ink_border}")
        decoration = f"BoxDecoration({', '.join(decoration_fields)})"
        return (
            "Material("
            "color: Colors.transparent, "
            f"child: Ink("
            f"decoration: {decoration}, "
            "child: InkWell("
            "onTap: () { /* <custom-code:button-action> */ }, "
            f"{custom_border}"
            f"child: {stack_widget}"
            ")"
            ")"
            ")"
        )
    if border_radius is None:
        return (
            "Material("
            "color: Colors.transparent, "
            f"child: InkWell(onTap: () {{ /* <custom-code:button-action> */ }}, child: {stack_widget})"
            ")"
        )
    return (
        "Material("
        "color: Colors.transparent, "
        f"borderRadius: BorderRadius.circular({border_radius}), "
        "clipBehavior: Clip.antiAlias, "
        "child: InkWell("
        "onTap: () { /* <custom-code:button-action> */ }, "
        f"borderRadius: BorderRadius.circular({border_radius}), "
        f"child: {stack_widget}"
        ")"
        ")"
    )


def wrap_back_nav_stack(stack_widget: str, *, theme_variant: str) -> str:
    if is_cupertino(theme_variant):
        return (
            f"GestureDetector("
            f"onTap: () {{ /* <custom-code:back-nav> */ }}, "
            f"behavior: HitTestBehavior.opaque, "
            f"child: {stack_widget}"
            f")"
        )
    return (
        "Material("
        "color: Colors.transparent, "
        "shape: const CircleBorder(), "
        "clipBehavior: Clip.antiAlias, "
        "child: InkWell("
        "customBorder: const CircleBorder(), "
        "onTap: () { /* <custom-code:back-nav> */ }, "
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
) -> str:
    stack = f"Stack(clipBehavior: Clip.none, children: [{body}])"
    wrapped = wrap_button_stack(
        stack,
        theme_variant=theme_variant,
        border_radius=border_radius,
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
