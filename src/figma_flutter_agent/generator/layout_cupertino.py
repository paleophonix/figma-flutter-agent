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
) -> str:
    if is_cupertino(theme_variant):
        gesture = (
            f"GestureDetector("
            f"onTap: () {{}}, "
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
    if border_radius is None:
        return (
            "Material("
            "color: Colors.transparent, "
            f"child: InkWell(onTap: () {{}}, child: {stack_widget})"
            ")"
        )
    return (
        "Material("
        "color: Colors.transparent, "
        f"borderRadius: BorderRadius.circular({border_radius}), "
        "clipBehavior: Clip.antiAlias, "
        "child: InkWell("
        "onTap: () {}, "
        f"borderRadius: BorderRadius.circular({border_radius}), "
        f"child: {stack_widget}"
        ")"
        ")"
    )


def wrap_button_children_stack(
    body: str,
    label: str,
    *,
    theme_variant: str,
) -> str:
    stack = f"Stack(clipBehavior: Clip.none, children: [{body}])"
    if is_cupertino(theme_variant):
        return (
            f"Semantics("
            f"label: '{label}', "
            f"child: GestureDetector("
            f"onTap: () {{}}, "
            f"behavior: HitTestBehavior.opaque, "
            f"child: {stack}"
            f")"
            f")"
        )
    return (
        f"Semantics("
        f"label: '{label}', "
        f"child: Material("
        f"color: Colors.transparent, "
        f"child: InkWell("
        f"onTap: () {{}}, "
        f"child: {stack},"
        f")"
        f")"
        f")"
    )


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
