"""Layout file assembly and deterministic screen shells."""

from __future__ import annotations

import re

from figma_flutter_agent.generator.cluster_variants import ClusterVectorVariant
from figma_flutter_agent.generator.layout.common import GEOMETRY_PLANNER_MARKER, to_pascal_case
from figma_flutter_agent.generator.layout.cupertino import wrap_layout_root
from figma_flutter_agent.generator.layout.file_methods import (
    chunk_dart_file_stem,
    compose_decomposed_root_widget,
    plan_layout_methods,
)
from figma_flutter_agent.generator.layout.file_preamble import (
    build_scaler_preamble,
    dart_ui_import_line,
    widget_import_lines_for_body,
)
from figma_flutter_agent.generator.layout.navigation.chrome import (
    ensure_layout_chrome_nav_helpers,
)
from figma_flutter_agent.generator.layout.responsive import responsive_emit_context
from figma_flutter_agent.generator.layout.widgets import (
    _stack_has_bottom_anchored_child,
    render_node_body,
    snap_device_pixels_scope,
)
from figma_flutter_agent.generator.paths import ImportContext
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeType,
)

_CHUNK_CLASS_REF_RE = re.compile(r"\b(FigmaChunk[A-F0-9]+)\b")


def _nested_chunk_import_lines(
    body: str,
    *,
    self_class_name: str,
    chunk_class_names: frozenset[str],
    feature_name: str,
    import_context: ImportContext,
) -> str:
    """Emit imports for sibling chunk widgets referenced inside a chunk body."""
    refs = {
        match
        for match in _CHUNK_CLASS_REF_RE.findall(body)
        if match != self_class_name and match in chunk_class_names
    }
    if not refs:
        return ""
    lines = ""
    for class_name in sorted(refs):
        stem = chunk_dart_file_stem(feature_name, class_name)
        lines += f"import '{import_context.uri(f'generated/{stem}.dart')}';\n"
    return f"{lines}\n"


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
    from figma_flutter_agent.generator.chunking import chunk_ir_tree

    chunking_result = chunk_ir_tree(tree)
    tree = chunking_result.root
    render_tree, wallpaper_children, shell_background_color = partition_wallpaper_foreground_tree(
        tree,
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

    methods = plan_layout_methods(tree)
    method_defs = ""
    chunk_bodies: list[tuple[str, str]] = []
    with (
        responsive_emit_context(
            enabled=responsive_enabled,
            design_artboard_width=design_artboard_width,
        ),
        snap_device_pixels_scope(snap_device_pixels),
    ):
        if methods is not None:
            layout_widget = compose_decomposed_root_widget(
                render_tree,
                methods,
                responsive_enabled=responsive_enabled,
                theme_variant=theme_variant,
            )
            blocks: list[str] = []
            decomposed_parent_type = render_tree.type
            pin_bottom_chrome = (
                render_tree.type == NodeType.STACK and _stack_has_bottom_anchored_child(render_tree)
            )
            from figma_flutter_agent.generator.layout.flex_policy.stack import (
                stack_child_should_use_pin_bottom_scroll_host,
            )

            for method in methods:
                scroll_content_root = pin_bottom_chrome and (
                    stack_child_should_use_pin_bottom_scroll_host(method.node)
                )
                body = render_node_body(
                    method.node,
                    is_layout_root=False,
                    parent_type=decomposed_parent_type,
                    parent_node=render_tree,
                    scroll_content_root=scroll_content_root,
                    **render_kwargs,
                )
                scaler = build_scaler_preamble(body)
                blocks.append(
                    f"  Widget {method.name}(BuildContext context) {{\n{scaler}    return {body};\n  }}\n"
                )
            method_defs = "\n" + "".join(blocks)
        else:
            layout_widget = render_node_body(render_tree, is_layout_root=True, **render_kwargs)
            if wallpaper_children:
                wallpaper_layer = render_screen_wallpaper_layer(
                    tree,
                    wallpaper_children,
                    uses_svg=uses_svg,
                )
                if wallpaper_layer is not None:
                    layout_widget = f"Stack(clipBehavior: Clip.none, children: [{wallpaper_layer}, {layout_widget}])"
        # Render extracted chunk subtrees inside the same pixel-snap scope.
        for _chunk_unit in chunking_result.chunks:
            _chunk_body = render_node_body(
                _chunk_unit.subtree, is_layout_root=False, **render_kwargs
            )
            chunk_bodies.append((_chunk_unit.class_name, _chunk_body))
    layout_widget = wrap_layout_root(
        layout_widget,
        theme_variant=theme_variant,
        background_color=(
            shell_background_color if wallpaper_children else tree.style.background_color
        ),
    )
    svg_import = "import 'package:flutter_svg/flutter_svg.dart';\n\n" if uses_svg else ""
    layout_path = f"lib/generated/{feature_name}_layout.dart"
    import_context = ImportContext(
        package_name=package_name,
        use_package_imports=use_package_imports,
        source_file=layout_path,
    )
    layout_body_for_imports = f"{layout_widget}{method_defs}"
    widget_import_lines = widget_import_lines_for_body(
        layout_body_for_imports,
        import_context=import_context,
        widget_imports=widget_imports,
        cluster_classes=cluster_classes,
    )
    if widget_import_lines and not widget_import_lines.endswith("\n\n"):
        widget_import_lines = f"{widget_import_lines}\n"
    from figma_flutter_agent.generator.layout.interactive import (
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
    from figma_flutter_agent.generator.layout.common import (
        ARTBOARD_PREVIEW_CLASS_FIELDS,
        ARTBOARD_PREVIEW_LAYOUT_MARKER,
    )

    build_scaler = build_scaler_preamble(layout_widget)
    full_emit_body = f"{layout_widget}{method_defs}"
    chrome_and_interactive = interactive_helpers
    layout_import = ""
    if "AppBreakpoints" in f"{full_emit_body}{chrome_and_interactive}":
        layout_import = f"import '{import_context.uri('theme/app_layout.dart')}';\n"
    dart_ui_import = dart_ui_import_line(full_emit_body)
    planner_marker = f"{GEOMETRY_PLANNER_MARKER}\n" if use_geometry_planner else ""
    artboard_preview_fields = (
        ARTBOARD_PREVIEW_CLASS_FIELDS if ARTBOARD_PREVIEW_LAYOUT_MARKER in layout_widget else ""
    )
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
{interactive_helpers}
/// Deterministic layout generated from the Figma clean design tree.
class {class_name} extends StatelessWidget {{
{artboard_preview_fields}  const {class_name}({{super.key}});

  @override
  Widget build(BuildContext context) {{
{build_scaler}    return {layout_widget};
  }}
{method_defs}}}
"""
    from figma_flutter_agent.generator.dart.llm_codegen import (
        _relax_tight_text_positioned_heights,
        expand_text_positioned_widths_from_tree,
        strip_tight_proportional_leading_in_text_styles,
    )

    layout_key = f"lib/generated/{feature_name}_layout.dart"
    content = strip_tight_proportional_leading_in_text_styles(content)
    content = _relax_tight_text_positioned_heights(content, render_tree)
    content = expand_text_positioned_widths_from_tree(content, render_tree)
    content = ensure_layout_chrome_nav_helpers(content, theme_variant=theme_variant)

    files: dict[str, str] = {layout_key: content}
    if chunk_bodies:
        # Inject imports for chunk files at the top of the layout custom-code zone.
        chunk_import_lines = ""
        for cn, _ in chunk_bodies:
            stem = chunk_dart_file_stem(feature_name, cn)
            chunk_import_lines += f"import '{import_context.uri(f'generated/{stem}.dart')}';\n"
        files[layout_key] = files[layout_key].replace(
            "// <custom-code>",
            f"{chunk_import_lines}// <custom-code>",
            1,
        )
        chunk_class_names = frozenset(cn for cn, _ in chunk_bodies)
        for cn, body in chunk_bodies:
            dart_ui = dart_ui_import_line(body)
            svg = (
                "import 'package:flutter_svg/flutter_svg.dart';\n\n"
                if uses_svg and "SvgPicture" in body
                else ""
            )
            scaler = build_scaler_preamble(body)
            chunk_stem = chunk_dart_file_stem(feature_name, cn)
            chunk_path = f"lib/generated/{chunk_stem}.dart"
            chunk_import_context = ImportContext(
                package_name=package_name,
                use_package_imports=use_package_imports,
                source_file=chunk_path,
            )
            chunk_widget_imports = widget_import_lines_for_body(
                body,
                import_context=chunk_import_context,
                widget_imports=widget_imports,
                cluster_classes=cluster_classes,
            )
            if chunk_widget_imports and not chunk_widget_imports.endswith("\n\n"):
                chunk_widget_imports = f"{chunk_widget_imports}\n"
            nested_chunk_imports = _nested_chunk_import_lines(
                body,
                self_class_name=cn,
                chunk_class_names=chunk_class_names,
                feature_name=feature_name,
                import_context=chunk_import_context,
            )
            chunk_content = (
                "// <auto-generated>\n"
                "// Generated by figma-flutter-agent. Do not edit by hand.\n"
                "// </auto-generated>\n\n"
                "import 'package:flutter/material.dart';\n\n"
                f"{dart_ui}{svg}{nested_chunk_imports}{chunk_widget_imports}"
                f"import '{chunk_import_context.uri('theme/app_colors.dart')}';\n"
                f"import '{chunk_import_context.uri('theme/app_spacing.dart')}';\n"
                f"import '{chunk_import_context.uri('theme/app_elevation.dart')}';\n\n"
                f"class {cn} extends StatelessWidget {{\n"
                f"  const {cn}({{super.key}});\n\n"
                "  @override\n"
                "  Widget build(BuildContext context) {\n"
                f"{scaler}    return {body};\n"
                "  }\n"
                "}\n"
            )
            chunk_content = ensure_layout_chrome_nav_helpers(
                chunk_content,
                theme_variant=theme_variant,
            )
            if uses_svg and "SvgPicture" in chunk_content and "flutter_svg" not in chunk_content:
                chunk_content = chunk_content.replace(
                    "import 'package:flutter/material.dart';\n",
                    "import 'package:flutter/material.dart';\n"
                    "import 'package:flutter_svg/flutter_svg.dart';\n",
                    1,
                )
            files[f"lib/generated/{chunk_stem}.dart"] = chunk_content
    return files
