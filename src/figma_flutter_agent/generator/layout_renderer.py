"""Layout file assembly and deterministic screen shells."""

from __future__ import annotations

from dataclasses import dataclass

from figma_flutter_agent.generator.cluster_variants import ClusterVectorVariant
from figma_flutter_agent.generator.layout_common import GEOMETRY_PLANNER_MARKER
from figma_flutter_agent.generator.layout_cupertino import wrap_layout_root
from figma_flutter_agent.generator.layout_navigation import (
    bottom_nav_stateful_helpers,
    first_node_id_of_type,
)
from figma_flutter_agent.generator.layout_style import box_decoration_expr
from figma_flutter_agent.generator.layout_widget import (
    _stack_has_bottom_anchored_child,
    _wrap_root_stack_viewport,
    render_node_body,
    snap_device_pixels_scope,
)
from figma_flutter_agent.generator.paths import Architecture, ImportContext
from figma_flutter_agent.generator.renderer import DartRenderer, to_pascal_case
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    FlutterGenerationResponse,
    NodeType,
)

__all__ = [
    "body_needs_dart_ui",
    "body_needs_text_scaler",
    "render_deterministic_screen_files",
    "render_layout_file",
    "render_node_body",
    "render_widget_file",
]

MAX_INLINE_LAYOUT_DEPTH = 7
_TEXT_SCALER_LINE = "    final textScaler = MediaQuery.textScalerOf(context);\n"
_TEXT_WIDGET_MARKERS = ("Text(", "RichText(", "Text.rich(", "TextField(")
_DART_UI_MARKERS = ("BackdropFilter(", "ImageFilter.blur", "Matrix4.")


def body_needs_dart_ui(body: str) -> bool:
    """Return True when generated layout code uses ``dart:ui`` symbols."""
    return any(marker in body for marker in _DART_UI_MARKERS)


def _dart_ui_import_line(body: str) -> str:
    """Build ``dart:ui`` import for blur and/or Matrix4 transforms."""
    needs_filter = "ImageFilter" in body or "BackdropFilter" in body
    needs_matrix = "Matrix4." in body
    if not needs_filter and not needs_matrix:
        return ""
    symbols: list[str] = []
    if needs_filter:
        symbols.append("ImageFilter")
    if needs_matrix:
        symbols.append("Matrix4")
    return f"import 'dart:ui' show {', '.join(symbols)};\n\n"


def body_needs_text_scaler(body: str) -> bool:
    """Return True when generated Dart body references text scaler locals."""
    return any(marker in body for marker in _TEXT_WIDGET_MARKERS)


def _build_scaler_preamble(body: str) -> str:
    if body_needs_text_scaler(body):
        return _TEXT_SCALER_LINE
    return ""


@dataclass(frozen=True)
class _LayoutMethod:
    """Private builder method extracted from a deep layout tree."""

    name: str
    node: CleanDesignTreeNode


def _tree_depth(node: CleanDesignTreeNode, depth: int = 1) -> int:
    if not node.children:
        return depth
    return max(_tree_depth(child, depth + 1) for child in node.children)


def _layout_method_name(node: CleanDesignTreeNode) -> str:
    base = to_pascal_case(node.name) or f"Section{node.id.replace(':', '')}"
    return f"_build{base}"


def _plan_layout_methods(tree: CleanDesignTreeNode) -> list[_LayoutMethod] | None:
    """Split deep layout trees into per-child private builder methods."""
    if _tree_depth(tree) <= MAX_INLINE_LAYOUT_DEPTH:
        return None
    if (
        tree.type not in {NodeType.STACK, NodeType.COLUMN, NodeType.ROW}
        or not tree.children
    ):
        return None
    used: set[str] = set()
    methods: list[_LayoutMethod] = []
    for index, child in enumerate(tree.children):
        name = _layout_method_name(child)
        if name in used:
            name = f"{name}{index + 1}"
        used.add(name)
        methods.append(_LayoutMethod(name=name, node=child))
    return methods


def _stack_method_call_expr(method: _LayoutMethod, *, pin_bottom_chrome: bool) -> str:
    """Wrap a decomposed stack layer for scroll + bottom-anchored chrome."""
    call = f"{method.name}(context)"
    if not pin_bottom_chrome:
        return call
    placement = method.node.stack_placement
    if placement is not None and placement.vertical == "BOTTOM":
        return call
    return f"Positioned.fill(child: SingleChildScrollView(child: {call}))"


def _compose_decomposed_root_widget(
    tree: CleanDesignTreeNode,
    methods: list[_LayoutMethod],
    *,
    responsive_enabled: bool,
) -> str:
    """Compose the root widget expression from extracted builder methods."""
    pin_bottom_chrome = tree.type == NodeType.STACK and _stack_has_bottom_anchored_child(
        tree
    )
    child_calls = (
        ", ".join(
            _stack_method_call_expr(method, pin_bottom_chrome=pin_bottom_chrome)
            for method in methods
        )
        or "const SizedBox.shrink()"
    )
    if tree.type == NodeType.STACK:
        widget = f"Stack(clipBehavior: Clip.hardEdge, children: [{child_calls}])"
        root_decoration = box_decoration_expr(
            tree.style,
            width=tree.sizing.width,
            height=tree.sizing.height,
        )
        if root_decoration is not None:
            widget = f"Container(decoration: {root_decoration}, child: {widget})"
        return _wrap_root_stack_viewport(tree, widget, is_layout_root=True)
    if tree.type == NodeType.COLUMN:
        return f"Column(crossAxisAlignment: CrossAxisAlignment.start, children: [{child_calls}])"
    if tree.type == NodeType.ROW:
        return f"Row(children: [{child_calls}])"
    return child_calls


def render_widget_file(
    *,
    class_name: str,
    body: str,
    uses_svg: bool,
    package_name: str = "demo_app",
    use_package_imports: bool = True,
    source_file: str = "lib/widgets/widget.dart",
    widget_fields: str = "",
    constructor_params: str = "{super.key}",
) -> str:
    """Render a reusable widget Dart file body."""
    import_context = ImportContext(
        package_name=package_name,
        use_package_imports=use_package_imports,
        source_file=source_file,
    )
    svg_import = "import 'package:flutter_svg/flutter_svg.dart';\n" if uses_svg else ""
    elevation_import = ""
    if "AppElevation" in body:
        elevation_import = (
            f"import '{import_context.uri('theme/app_elevation.dart')}';\n"
        )
    layout_import = ""
    if "AppBreakpoints" in body:
        layout_import = f"import '{import_context.uri('theme/app_layout.dart')}';\n"
    scaler_preamble = _build_scaler_preamble(body)
    return f"""// <auto-generated>
// Generated by figma-flutter-agent. Do not edit by hand.
// </auto-generated>

import 'package:flutter/material.dart';
{svg_import}
import '{import_context.uri("theme/app_colors.dart")}';
import '{import_context.uri("theme/app_spacing.dart")}';
{layout_import}{elevation_import}
// <custom-code>
// </custom-code>

class {class_name} extends StatelessWidget {{
{widget_fields}  const {class_name}({constructor_params});

  @override
  Widget build(BuildContext context) {{
{scaler_preamble}    return {body};
  }}
}}
"""


def render_layout_file(
    tree: CleanDesignTreeNode,
    *,
    skip_layout_reconcile: bool = False,
    feature_name: str,
    uses_svg: bool,
    cluster_classes: dict[str, str] | None = None,
    cluster_vector_variants: dict[str, ClusterVectorVariant] | None = None,
    widget_imports: list[str] | None = None,
    package_name: str = "demo_app",
    use_package_imports: bool = True,
    theme_variant: str = "material_3",
    responsive_enabled: bool = True,
    snap_device_pixels: bool = False,
    bundled_font_families: frozenset[str] | None = None,
    dart_weight_overrides_by_family: dict[str, dict[str, str]] | None = None,
    text_theme_slot_by_style_name: dict[str, str] | None = None,
    text_theme_size_slots: list[tuple[float, str]] | None = None,
    de_archetype_pass: bool = False,
    use_geometry_planner: bool = False,
) -> dict[str, str]:
    """Render deterministic layout Dart for a clean design tree."""
    from figma_flutter_agent.generator.ambient_background import (
        partition_wallpaper_foreground_tree,
        render_screen_wallpaper_layer,
    )
    if not skip_layout_reconcile:
        from figma_flutter_agent.generator.normalize import reconcile_layout_tree

        tree = reconcile_layout_tree(tree)
    render_tree, wallpaper_children, shell_background_color = (
        partition_wallpaper_foreground_tree(
            tree,
        )
    )
    class_name = f"{to_pascal_case(feature_name)}Layout"
    design_artboard_width = render_tree.sizing.width
    if design_artboard_width is not None and design_artboard_width <= 0:
        design_artboard_width = None
    render_kwargs = {
        "uses_svg": uses_svg,
        "cluster_classes": cluster_classes,
        "cluster_vector_variants": cluster_vector_variants,
        "theme_variant": theme_variant,
        "responsive_enabled": responsive_enabled,
        "design_artboard_width": design_artboard_width,
        "bundled_font_families": bundled_font_families,
        "dart_weight_overrides_by_family": dart_weight_overrides_by_family,
        "text_theme_slot_by_style_name": text_theme_slot_by_style_name,
        "text_theme_size_slots": text_theme_size_slots,
        "de_archetype_pass": de_archetype_pass,
    }
    from figma_flutter_agent.generator.ambient_background import (
        partition_wallpaper_foreground_tree,
    )

    methods = _plan_layout_methods(tree)
    method_defs = ""
    with snap_device_pixels_scope(snap_device_pixels):
        if methods is not None:
            layout_widget = _compose_decomposed_root_widget(
                render_tree,
                methods,
                responsive_enabled=responsive_enabled,
            )
            blocks: list[str] = []
            decomposed_parent_type = render_tree.type
            for method in methods:
                body = render_node_body(
                    method.node,
                    is_layout_root=False,
                    parent_type=decomposed_parent_type,
                    parent_node=render_tree,
                    **render_kwargs,
                )
                scaler = _build_scaler_preamble(body)
                blocks.append(
                    f"  Widget {method.name}(BuildContext context) {{\n{scaler}    return {body};\n  }}\n"
                )
            method_defs = "\n" + "".join(blocks)
        else:
            layout_widget = render_node_body(
                render_tree, is_layout_root=True, **render_kwargs
            )
            if wallpaper_children:
                wallpaper_layer = render_screen_wallpaper_layer(
                    tree,
                    wallpaper_children,
                    uses_svg=uses_svg,
                )
                if wallpaper_layer is not None:
                    layout_widget = f"Stack(clipBehavior: Clip.none, children: [{wallpaper_layer}, {layout_widget}])"
    if tree.type == NodeType.STACK:
        layout_widget = wrap_layout_root(
            layout_widget,
            theme_variant=theme_variant,
            background_color=(
                shell_background_color
                if wallpaper_children
                else tree.style.background_color
            ),
        )
    svg_import = (
        "import 'package:flutter_svg/flutter_svg.dart';\n\n" if uses_svg else ""
    )
    layout_path = f"lib/generated/{feature_name}_layout.dart"
    import_context = ImportContext(
        package_name=package_name,
        use_package_imports=use_package_imports,
        source_file=layout_path,
    )
    widget_import_lines = ""
    if widget_imports:
        widget_import_lines = "".join(
            f"import '{import_context.uri(f'widgets/{file_name}.dart')}';\n"
            for file_name in sorted(set(widget_imports))
        )
        if widget_import_lines:
            widget_import_lines += "\n"
    bottom_nav_helpers = ""
    bottom_nav_id = first_node_id_of_type(tree, NodeType.BOTTOM_NAV)
    if bottom_nav_id is not None:
        bottom_nav_helpers = (
            f"{bottom_nav_stateful_helpers(theme_variant=theme_variant, node_id=bottom_nav_id)}\n"
        )
    from figma_flutter_agent.generator.layout_interactive import (
        interactive_layout_helpers,
    )

    interactive_helpers = interactive_layout_helpers(tree)
    if interactive_helpers:
        interactive_helpers = f"{interactive_helpers}\n"
    cupertino_import = (
        "import 'package:flutter/cupertino.dart';\n\n"
        if theme_variant == "cupertino" or interactive_helpers
        else ""
    )
    layout_import = ""
    if responsive_enabled:
        layout_import = f"import '{import_context.uri('theme/app_layout.dart')}';\n"
    build_scaler = _build_scaler_preamble(layout_widget)
    full_emit_body = f"{layout_widget}{method_defs}"
    dart_ui_import = _dart_ui_import_line(full_emit_body)
    planner_marker = f"{GEOMETRY_PLANNER_MARKER}\n" if use_geometry_planner else ""
    content = f"""// <auto-generated>
// Generated by figma-flutter-agent. Do not edit by hand.
// </auto-generated>
{planner_marker}
import 'package:flutter/material.dart';
import 'package:flutter/gestures.dart';

{dart_ui_import}{cupertino_import}{svg_import}import '{import_context.uri("theme/app_colors.dart")}';
import '{import_context.uri("theme/app_spacing.dart")}';
import '{import_context.uri("theme/app_elevation.dart")}';
{layout_import}{widget_import_lines}// <custom-code>
// </custom-code>
{bottom_nav_helpers}{interactive_helpers}
/// Deterministic layout generated from the Figma clean design tree.
class {class_name} extends StatelessWidget {{
  const {class_name}({{super.key}});

  @override
  Widget build(BuildContext context) {{
{build_scaler}    return {layout_widget};
  }}
}}{method_defs}
"""
    from figma_flutter_agent.generator.llm_dart import (
        _relax_tight_text_positioned_heights,
        expand_text_positioned_widths_from_tree,
        strip_tight_proportional_leading_in_text_styles,
    )

    layout_key = f"lib/generated/{feature_name}_layout.dart"
    content = strip_tight_proportional_leading_in_text_styles(content)
    content = _relax_tight_text_positioned_heights(content, render_tree)
    content = expand_text_positioned_widths_from_tree(content, render_tree)
    return {layout_key: content}


def _screen_app_bar_title(feature_name: str) -> str:
    """Human-readable title for generated AppBar."""
    return feature_name.replace("_", " ").strip().title() or "Screen"


def render_deterministic_screen_files(
    *,
    feature_name: str,
    screen_class: str,
    uses_svg: bool,
    use_auto_route: bool,
    responsive_enabled: bool,
    max_web_width: int,
    shell_safe_area: bool = False,
    cluster_widget_imports: list[str] | None = None,
    architecture: Architecture = "feature_first",
    package_name: str = "demo_app",
    use_package_imports: bool = True,
    state_management_type: str = "none",
    use_scaffold: bool = True,
    theme_variant: str = "material_3",
) -> dict[str, str]:
    """Render a screen that delegates UI to the deterministic layout file."""
    from figma_flutter_agent.generator.layout_cupertino import screen_shell_dart

    renderer = DartRenderer()
    layout_class = f"{to_pascal_case(feature_name)}Layout"
    if responsive_enabled:
        body = f"GeneratedScreenShell(child: const {layout_class}())"
    else:
        body = f"const {layout_class}()"
    title = _screen_app_bar_title(feature_name)
    root_widget, screen_scaler = screen_shell_dart(
        body=body,
        theme_variant=theme_variant,
        use_scaffold=use_scaffold,
        title=title,
        needs_scaler_preamble=body_needs_text_scaler(body) or use_scaffold,
    )
    auto_route = "@RoutePage()\n" if use_auto_route else ""
    screen_code = f"""{auto_route}class {screen_class} extends StatelessWidget {{
  const {screen_class}({{super.key}});

  @override
  Widget build(BuildContext context) {{
{screen_scaler}    return {root_widget};
  }}
}}"""
    return renderer.render_generation_files(
        FlutterGenerationResponse(screen_code=screen_code),
        feature_name=feature_name,
        uses_svg=uses_svg,
        use_auto_route=use_auto_route,
        responsive_enabled=responsive_enabled,
        shell_safe_area=shell_safe_area,
        max_web_width=max_web_width,
        layout_import=f"{feature_name}_layout",
        extra_widget_imports=cluster_widget_imports,
        screen_only=True,
        architecture=architecture,
        package_name=package_name,
        use_package_imports=use_package_imports,
        state_management_type=state_management_type,
    )
