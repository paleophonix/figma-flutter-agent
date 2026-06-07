"""Emit Dart widget expressions and screen classes from screen IR."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from loguru import logger

from figma_flutter_agent.errors import GenerationError
from figma_flutter_agent.generator.cluster_variants import ClusterVectorVariant
from figma_flutter_agent.generator.ir.tree import index_clean_tree, merge_screen_ir
from figma_flutter_agent.generator.ir.validate import (
    apply_ir_guards,
    validate_extracted_widgets,
    validate_screen_ir,
)
from figma_flutter_agent.generator.layout.common import to_pascal_case, to_snake_case
from figma_flutter_agent.generator.layout.flex_policy import (
    FlexWrapKind,
    apply_flex_wrap_to_widget,
    emit_flexible_loose,
)
from figma_flutter_agent.generator.layout.renderer import (
    render_node_body,
    render_widget_file,
)
from figma_flutter_agent.generator.dart.llm_codegen import (
    _canonical_widget_class_name,
    normalize_llm_extracted_widget_code,
)
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    DesignTokens,
    ExtractedWidget,
    FlexWrapIr,
    FlutterGenerationResponse,
    NodeType,
    ScreenIr,
    WidgetIrKind,
    WidgetIrNode,
)


@dataclass(frozen=True)
class IrEmitPolicy:
    """Controls IR validation and auto-guards before Dart emission."""

    apply_guards: bool = True
    validate: bool = True


@dataclass(frozen=True)
class IrEmitContext:
    """Codegen context shared with deterministic layout rendering."""

    uses_svg: bool = False
    cluster_classes: dict[str, str] | None = None
    cluster_vector_variants: dict[str, ClusterVectorVariant] | None = None
    theme_variant: str = "material_3"
    responsive_enabled: bool = True
    is_layout_root: bool = True
    bundled_font_families: frozenset[str] | None = None
    dart_weight_overrides_by_family: dict[str, dict[str, str]] | None = None
    text_theme_slot_by_style_name: dict[str, str] | None = None
    text_theme_size_slots: list[tuple[float, str]] | None = None
    policy: IrEmitPolicy = IrEmitPolicy()


_FLEX_WRAP_IR_TO_KIND: dict[FlexWrapIr, FlexWrapKind] = {
    FlexWrapIr.NONE: FlexWrapKind.NONE,
    FlexWrapIr.EXPANDED: FlexWrapKind.EXPANDED,
    FlexWrapIr.FLEXIBLE_LOOSE: FlexWrapKind.FLEXIBLE_LOOSE,
    FlexWrapIr.SIZED_BOX_WIDTH: FlexWrapKind.SIZED_BOX_WIDTH,
}


def _render_kwargs(ctx: IrEmitContext) -> dict[str, object]:
    return {
        "uses_svg": ctx.uses_svg,
        "cluster_classes": ctx.cluster_classes,
        "cluster_vector_variants": ctx.cluster_vector_variants,
        "theme_variant": ctx.theme_variant,
        "responsive_enabled": ctx.responsive_enabled,
        "bundled_font_families": ctx.bundled_font_families,
        "dart_weight_overrides_by_family": ctx.dart_weight_overrides_by_family,
        "text_theme_slot_by_style_name": ctx.text_theme_slot_by_style_name,
        "text_theme_size_slots": ctx.text_theme_size_slots,
    }


def _emit_extracted_ref(
    ir: WidgetIrNode,
    *,
    extracted_class_by_widget_name: dict[str, str] | None = None,
) -> str:
    ref = ir.ref
    if ref is None or not ref.widget_name.strip():
        return "const SizedBox.shrink()"
    class_name = ref.widget_name.strip()
    if extracted_class_by_widget_name:
        class_name = extracted_class_by_widget_name.get(class_name, class_name)
    else:
        class_name = _canonical_widget_class_name(class_name)
    args = ", ".join(f"{name}: {_format_ir_arg(value)}" for name, value in ref.named_args.items())
    if args:
        return f"{class_name}({args})"
    return f"{class_name}()"


def _format_ir_arg(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace("'", "\\'")
        return f"'{escaped}'"
    return repr(value)


def _apply_ir_wrap(
    widget: str,
    *,
    ir: WidgetIrNode,
    parent_type: NodeType | None,
    clean: CleanDesignTreeNode,
) -> str:
    if ir.wrap is not None:
        kind = _FLEX_WRAP_IR_TO_KIND.get(ir.wrap, FlexWrapKind.NONE)
        if kind == FlexWrapKind.NONE:
            return widget
        if kind == FlexWrapKind.EXPANDED:
            return f"Expanded(child: {widget})"
        if kind == FlexWrapKind.FLEXIBLE_LOOSE:
            return emit_flexible_loose(widget)
        if kind == FlexWrapKind.SIZED_BOX_WIDTH:
            from figma_flutter_agent.generator.layout.flex_policy import (
                wrap_column_child_width_fill,
            )

            return wrap_column_child_width_fill(widget, clean)
    return apply_flex_wrap_to_widget(widget, parent_type=parent_type, node=clean)


def _build_extracted_class_map(
    widgets: list[ExtractedWidget],
) -> dict[str, str]:
    pairs = [
        (widget.widget_name.strip(), widget.resolved_code())
        for widget in widgets
        if widget.widget_name.strip() and widget.resolved_code()
    ]
    if pairs:
        from figma_flutter_agent.generator.dart.llm_codegen import (
            _WIDGET_CLASS_RE,
            prepare_llm_extracted_widgets,
        )

        prepared, _ = prepare_llm_extracted_widgets(pairs)
        mapping: dict[str, str] = {}
        for widget_name, code in prepared:
            match = _WIDGET_CLASS_RE.search(code)
            mapping[widget_name] = (
                match.group("name") if match else _canonical_widget_class_name(widget_name)
            )
        return mapping
    mapping = {}
    for widget in widgets:
        name = widget.widget_name.strip()
        if not name:
            continue
        mapping[name] = _canonical_widget_class_name(name)
    return mapping


def emit_widget_expression(
    ir: WidgetIrNode,
    *,
    clean: CleanDesignTreeNode,
    parent_type: NodeType | None,
    ctx: IrEmitContext,
    extracted_class_by_widget_name: dict[str, str] | None = None,
) -> str:
    """Emit a Dart widget expression for one IR node."""
    if ir.kind == WidgetIrKind.EXTRACTED:
        return _emit_extracted_ref(
            ir,
            extracted_class_by_widget_name=extracted_class_by_widget_name,
        )

    kwargs = _render_kwargs(ctx)
    widget = render_node_body(
        clean,
        parent_type=parent_type,
        is_layout_root=ctx.is_layout_root and parent_type is None,
        **kwargs,
    )
    return _apply_ir_wrap(widget, ir=ir, parent_type=parent_type, clean=clean)


def emit_merged_root_expression(
    merged_root: CleanDesignTreeNode,
    *,
    ctx: IrEmitContext,
) -> str:
    """Emit the root widget expression from a merged clean tree."""
    return render_node_body(
        merged_root,
        is_layout_root=ctx.is_layout_root,
        **_render_kwargs(ctx),
    )


def emit_screen_code_from_ir(
    screen_ir: ScreenIr,
    *,
    clean_tree: CleanDesignTreeNode,
    screen_class: str,
    ctx: IrEmitContext,
    use_auto_route: bool = False,
    use_scaffold: bool = True,
    app_bar_title: str | None = None,
    responsive_shell: bool = False,
    extracted_class_by_widget_name: dict[str, str] | None = None,
    project_dir: Path | None = None,
    tokens: DesignTokens | None = None,
) -> str:
    """Compile ``ScreenIr`` into a ``StatelessWidget`` Dart class (screenCode shape)."""
    if ctx.policy.validate:
        clean_tree = validate_screen_ir(
            screen_ir,
            clean_tree,
            project_dir=project_dir,
            tokens=tokens,
            apply_guards=ctx.policy.apply_guards,
        )
    elif ctx.policy.apply_guards:
        clean_tree = apply_ir_guards(screen_ir, clean_tree, tokens=tokens)
    merged = merge_screen_ir(
        clean_tree,
        screen_ir,
        extracted_class_by_widget_name=extracted_class_by_widget_name,
    )
    from figma_flutter_agent.generator.layout.cupertino import screen_shell_dart
    from figma_flutter_agent.generator.layout.renderer import body_needs_text_scaler

    body = emit_merged_root_expression(merged, ctx=ctx)
    if responsive_shell:
        body = f"GeneratedScreenShell(child: {body})"
    root_widget, screen_scaler = screen_shell_dart(
        body=body,
        theme_variant=ctx.theme_variant,
        use_scaffold=use_scaffold,
        title=app_bar_title or "Screen",
        needs_scaler_preamble=body_needs_text_scaler(body) or use_scaffold,
    )
    auto_route = "@RoutePage()\n" if use_auto_route else ""
    return f"""{auto_route}class {screen_class} extends StatelessWidget {{
  const {screen_class}({{super.key}});

  @override
  Widget build(BuildContext context) {{
{screen_scaler}    return {root_widget};
  }}
}}"""


def emit_extracted_widget_code_from_ir(
    widget_ir: WidgetIrNode,
    *,
    clean_tree: CleanDesignTreeNode,
    widget_name: str,
    ctx: IrEmitContext,
    project_dir: Path | None = None,
    tokens: DesignTokens | None = None,
) -> str:
    """Compile one extracted widget IR subtree into a widget Dart file."""
    tree_by_id = index_clean_tree(clean_tree)
    subtree = tree_by_id.get(widget_ir.figma_id)
    if subtree is None:
        raise GenerationError(
            f"widgetIr figmaId {widget_ir.figma_id!r} not found in clean tree"
        )
    widget_ir_screen = ScreenIr(root=widget_ir)
    if ctx.policy.validate:
        clean_tree = validate_screen_ir(
            widget_ir_screen,
            clean_tree,
            project_dir=project_dir,
            tokens=tokens,
            apply_guards=ctx.policy.apply_guards,
        )
        subtree = index_clean_tree(clean_tree).get(widget_ir.figma_id) or subtree
    elif ctx.policy.apply_guards:
        clean_tree = apply_ir_guards(widget_ir_screen, clean_tree, tokens=tokens)
        subtree = index_clean_tree(clean_tree).get(widget_ir.figma_id) or subtree
    merged = merge_screen_ir(
        subtree,
        widget_ir_screen,
        extracted_class_by_widget_name={
            widget_name: _canonical_widget_class_name(widget_name),
        },
    )
    widget_ctx = IrEmitContext(
        uses_svg=ctx.uses_svg,
        cluster_classes=ctx.cluster_classes,
        cluster_vector_variants=ctx.cluster_vector_variants,
        theme_variant=ctx.theme_variant,
        responsive_enabled=ctx.responsive_enabled,
        is_layout_root=True,
        bundled_font_families=ctx.bundled_font_families,
        dart_weight_overrides_by_family=ctx.dart_weight_overrides_by_family,
        text_theme_slot_by_style_name=ctx.text_theme_slot_by_style_name,
        text_theme_size_slots=ctx.text_theme_size_slots,
    )
    body = emit_merged_root_expression(merged, ctx=widget_ctx)
    class_name = _canonical_widget_class_name(widget_name)
    file_stem = to_snake_case(widget_name)
    return render_widget_file(
        class_name=class_name,
        body=body,
        uses_svg=ctx.uses_svg,
        source_file=f"lib/widgets/{file_stem}.dart",
    )


def _materialize_extracted_widgets(
    widgets: list[ExtractedWidget],
    *,
    clean_tree: CleanDesignTreeNode,
    ctx: IrEmitContext,
    prefer_existing_code: bool = True,
    project_dir: Path | None = None,
    tokens: DesignTokens | None = None,
) -> list[ExtractedWidget]:
    tree_by_id = index_clean_tree(clean_tree)
    materialized: list[ExtractedWidget] = []
    for widget in widgets:
        if widget.widget_ir is None:
            materialized.append(widget)
            continue
        if prefer_existing_code and widget.resolved_code():
            materialized.append(widget)
            continue
        if widget.widget_ir.figma_id not in tree_by_id:
            logger.warning(
                "Skipping widgetIr materialization for {}: figmaId {} absent from clean tree "
                "(likely true_subtree_pruning); rely on deterministic lib/widgets code",
                widget.widget_name,
                widget.widget_ir.figma_id,
            )
            materialized.append(widget)
            continue
        code = emit_extracted_widget_code_from_ir(
            widget.widget_ir,
            clean_tree=clean_tree,
            widget_name=widget.widget_name,
            ctx=ctx,
            project_dir=project_dir,
            tokens=tokens,
        )
        materialized.append(
            widget.model_copy(
                update={
                    "code": code,
                },
            ),
        )
    return materialized


def materialize_screen_code_from_ir(
    generation: FlutterGenerationResponse,
    *,
    clean_tree: CleanDesignTreeNode,
    feature_name: str,
    ctx: IrEmitContext,
    use_auto_route: bool = False,
    use_scaffold: bool = True,
    responsive_shell: bool = False,
    prefer_existing_screen_code: bool = False,
    materialize_screen_body: bool = True,
    materialize_extracted: bool = True,
    prefer_existing_extracted_code: bool = True,
    project_dir: Path | None = None,
    tokens: DesignTokens | None = None,
) -> FlutterGenerationResponse:
    """Resolve IR fields into Dart for the existing planner/renderer path."""
    extracted_names = frozenset(widget.widget_name for widget in generation.extracted_widgets)
    if generation.screen_ir is not None:
        from figma_flutter_agent.generator.ir.presence import normalize_screen_ir_presence

        screen_ir = normalize_screen_ir_presence(
            generation.screen_ir,
            clean_tree,
            extracted_widget_names=extracted_names,
        )
        if screen_ir is not generation.screen_ir:
            generation = generation.model_copy(update={"screen_ir": screen_ir})
        if ctx.policy.validate:
            clean_tree = validate_screen_ir(
                generation.screen_ir,
                clean_tree,
                extracted_widget_names=extracted_names,
                project_dir=project_dir,
                tokens=tokens,
                apply_guards=ctx.policy.apply_guards,
            )
        elif ctx.policy.apply_guards:
            clean_tree = apply_ir_guards(
                generation.screen_ir, clean_tree, tokens=tokens
            )
        if project_dir is not None:
            from figma_flutter_agent.debug.ir_dumps import write_screen_ir_snapshot

            write_screen_ir_snapshot(
                stage="pre_emit",
                feature_name=feature_name,
                screen_ir=generation.screen_ir,
                extracted_widgets=generation.extracted_widgets or None,
                project_dir=project_dir,
            )
    if materialize_extracted and generation.extracted_widgets:
        validate_extracted_widgets(
            generation.extracted_widgets,
            clean_tree,
            project_dir=project_dir,
            tokens=tokens,
        )
        widgets = _materialize_extracted_widgets(
            generation.extracted_widgets,
            clean_tree=clean_tree,
            ctx=ctx,
            prefer_existing_code=prefer_existing_extracted_code,
            project_dir=project_dir,
            tokens=tokens,
        )
        generation = generation.model_copy(update={"extracted_widgets": widgets})

    if generation.screen_ir is None or not materialize_screen_body:
        return generation
    if prefer_existing_screen_code and generation.resolved_screen_code():
        return generation

    extracted_class_map = _build_extracted_class_map(generation.extracted_widgets)
    screen_class = f"{to_pascal_case(feature_name)}Screen"
    title = feature_name.replace("_", " ").strip().title() or "Screen"
    screen_code = emit_screen_code_from_ir(
        generation.screen_ir,
        clean_tree=clean_tree,
        screen_class=screen_class,
        ctx=ctx,
        use_auto_route=use_auto_route,
        use_scaffold=use_scaffold,
        app_bar_title=title,
        responsive_shell=responsive_shell,
        extracted_class_by_widget_name=extracted_class_map,
        project_dir=project_dir,
        tokens=tokens,
    )
    from figma_flutter_agent.generator.dart.file_parts import strip_directives_from_fragment
    from figma_flutter_agent.generator.dart.llm_codegen import apply_clean_tree_text_to_screen

    screen_code = strip_directives_from_fragment(
        apply_clean_tree_text_to_screen(screen_code, clean_tree),
    )
    return generation.model_copy(
        update={
            "screen_code": screen_code,
        },
    )


materialize_generation_from_ir = materialize_screen_code_from_ir


__all__ = [
    "IrEmitContext",
    "IrEmitPolicy",
    "emit_extracted_widget_code_from_ir",
    "emit_merged_root_expression",
    "emit_screen_code_from_ir",
    "emit_widget_expression",
    "materialize_generation_from_ir",
    "materialize_screen_code_from_ir",
]
