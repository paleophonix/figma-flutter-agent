"""Dart expression emission from screen IR nodes."""

from __future__ import annotations

from dataclasses import dataclass

from loguru import logger

from figma_flutter_agent.generator.dart.llm_codegen import _canonical_widget_class_name
from figma_flutter_agent.generator.ir.context import IrEmitContext, render_kwargs
from figma_flutter_agent.generator.ir.semantic_emit import emit_semantic_widget
from figma_flutter_agent.generator.ir.tree import index_ir_tree
from figma_flutter_agent.generator.layout.flex_policy import (
    FlexWrapKind,
    apply_flex_wrap_to_widget,
    emit_flexible_loose,
)
from figma_flutter_agent.generator.layout.widgets.emit.shell import (
    build_flow_context,
    build_render_ctx,
    prepare_layout_children,
    render_layout_shell,
    render_leaf_body,
)
from figma_flutter_agent.schemas import (
    SEMANTIC_MVP_IR_KINDS,
    STUB_IR_KINDS,
    CleanDesignTreeNode,
    FlexWrapIr,
    NodeType,
    ScreenIr,
    WidgetIrKind,
    WidgetIrNode,
)

_STRUCTURAL_NODE_TYPES = frozenset(
    {
        NodeType.COLUMN,
        NodeType.ROW,
        NodeType.STACK,
        NodeType.GRID,
        NodeType.WRAP,
    }
)


def _semantic_mvp_emit_enabled(ctx: IrEmitContext) -> bool:
    """Return True when MVP semantic templates may replace layout emit."""
    if ctx.semantic_report_only is not None:
        return not ctx.semantic_report_only
    return not ctx.semantics.report_only


_FLEX_WRAP_IR_TO_KIND: dict[FlexWrapIr, FlexWrapKind] = {
    FlexWrapIr.NONE: FlexWrapKind.NONE,
    FlexWrapIr.EXPANDED: FlexWrapKind.EXPANDED,
    FlexWrapIr.FLEXIBLE_LOOSE: FlexWrapKind.FLEXIBLE_LOOSE,
    FlexWrapIr.SIZED_BOX_WIDTH: FlexWrapKind.SIZED_BOX_WIDTH,
}


@dataclass(frozen=True)
class IrEmitWalkState:
    """IR-indexed walk state for screen-body emission."""

    ir_by_id: dict[str, WidgetIrNode]
    ctx: IrEmitContext
    extracted_class_by_widget_name: dict[str, str] | None = None
    figma_id_to_widget_name: dict[str, str] | None = None


def _should_ir_walk_children(clean: CleanDesignTreeNode) -> bool:
    return bool(clean.children) and clean.type in _STRUCTURAL_NODE_TYPES


def _resolve_ir_node(figma_id: str, walk: IrEmitWalkState) -> WidgetIrNode:
    return walk.ir_by_id.get(figma_id) or WidgetIrNode(figma_id=figma_id)


def emit_widget_expression(
    ir: WidgetIrNode,
    *,
    clean: CleanDesignTreeNode,
    parent_type: NodeType | None,
    ctx: IrEmitContext,
    extracted_class_by_widget_name: dict[str, str] | None = None,
    walk: IrEmitWalkState | None = None,
    parent_node: CleanDesignTreeNode | None = None,
    scroll_content_root: bool = False,
) -> str:
    """Emit a Dart widget expression for one IR node."""
    if ir.kind == WidgetIrKind.EXTRACTED:
        figma_map = (
            walk.figma_id_to_widget_name if walk is not None else None
        )
        return emit_extracted_ref(
            ir,
            extracted_class_by_widget_name=extracted_class_by_widget_name,
            figma_id_to_widget_name=figma_map,
        )
    if ir.kind == WidgetIrKind.CHIP_CHOICE:
        from figma_flutter_agent.generator.layout.widgets.option_chip import (
            emit_chip_choice_layout,
        )

        widget = emit_chip_choice_layout(ir, clean=clean, ctx=ctx)
        return apply_ir_wrap(widget, ir=ir, parent_type=parent_type, clean=clean)
    if ir.kind in SEMANTIC_MVP_IR_KINDS and _semantic_mvp_emit_enabled(ctx):
        from figma_flutter_agent.generator.ir.fidelity import (
            EmitPath,
            emit_styled_primitive,
            route_by_fidelity_tier,
            tier_allows_native,
        )

        semantics = ctx.semantics
        emit_path = route_by_fidelity_tier(
            ir,
            ctx=ctx,
            strict_fidelity=semantics.strict_fidelity,
            strict_l10n=semantics.strict_l10n,
            strict_a11y=semantics.strict_a11y,
        )
        if emit_path == EmitPath.NATIVE_TEMPLATE and tier_allows_native(ir.fidelity_tier):
            widget = emit_semantic_widget(ir, clean=clean, ctx=ctx)
            return apply_ir_wrap(widget, ir=ir, parent_type=parent_type, clean=clean)
        if emit_path == EmitPath.STYLED_PRIMITIVE:
            widget = emit_styled_primitive(ir, clean=clean, ctx=ctx)
            return apply_ir_wrap(widget, ir=ir, parent_type=parent_type, clean=clean)
        if emit_path == EmitPath.BAKED_ASSET:
            from figma_flutter_agent.generator.ir.fidelity.baked_gate import evaluate_baked_emit
            from figma_flutter_agent.generator.ir.fidelity.router import FidelityRoutePolicy

            baked_decision = evaluate_baked_emit(
                ir,
                clean=clean,
                policy=FidelityRoutePolicy(
                    strict_fidelity=semantics.strict_fidelity,
                    strict_l10n=semantics.strict_l10n,
                    strict_a11y=semantics.strict_a11y,
                ),
            )
            if baked_decision.emit_path == EmitPath.STYLED_PRIMITIVE:
                widget = emit_styled_primitive(ir, clean=clean, ctx=ctx)
                return apply_ir_wrap(widget, ir=ir, parent_type=parent_type, clean=clean)
            from figma_flutter_agent.generator.ir.fidelity.baked_emit import emit_baked_asset

            widget = emit_baked_asset(ir, clean=clean, ctx=ctx)
            return apply_ir_wrap(widget, ir=ir, parent_type=parent_type, clean=clean)
    if ir.kind in STUB_IR_KINDS:
        logger.warning(
            "Stub IR kind {} for figmaId {}; falling back to layout emit",
            ir.kind.value,
            ir.figma_id,
        )

    kwargs = render_kwargs(ctx)
    is_layout_root = ctx.is_layout_root and parent_type is None
    effective_walk = walk
    effective_extracted = extracted_class_by_widget_name
    if effective_walk is not None:
        effective_extracted = effective_extracted or effective_walk.extracted_class_by_widget_name

    if effective_walk is not None and _should_ir_walk_children(clean):
        widget = _emit_ir_layout_container(
            ir,
            clean,
            parent_type=parent_type,
            parent_node=parent_node,
            is_layout_root=is_layout_root,
            scroll_content_root=scroll_content_root,
            walk=effective_walk,
            extracted_class_by_widget_name=effective_extracted,
            **kwargs,
        )
    else:
        widget = render_leaf_body(
            clean,
            parent_type=parent_type,
            parent_node=parent_node,
            is_layout_root=is_layout_root,
            scroll_content_root=scroll_content_root,
            **kwargs,
        )
    return apply_ir_wrap(widget, ir=ir, parent_type=parent_type, clean=clean)


def _emit_ir_layout_container(
    _ir: WidgetIrNode,
    clean: CleanDesignTreeNode,
    *,
    parent_type: NodeType | None,
    parent_node: CleanDesignTreeNode | None,
    is_layout_root: bool,
    scroll_content_root: bool,
    walk: IrEmitWalkState,
    extracted_class_by_widget_name: dict[str, str] | None,
    **kwargs: object,
) -> str:
    """Emit a structural container with IR-aware child expressions."""
    (
        sorted_children,
        metadata_column_host,
        paired_circle_ids,
        omit_child_ids,
        playback_seek_ids,
        playback_decor_omit_ids,
        merged_thumb_widgets,
    ) = prepare_layout_children(
        clean,
        is_layout_root=is_layout_root,
        parent_node=parent_node,
    )

    def ir_recurse(
        child: CleanDesignTreeNode,
        *,
        parent_type: NodeType | None = None,
        parent_node: CleanDesignTreeNode | None = None,
        scroll_content_root: bool = False,
        **_child_kwargs: object,
    ) -> str:
        child_ir = _resolve_ir_node(child.id, walk)
        return emit_widget_expression(
            child_ir,
            clean=child,
            parent_type=parent_type or clean.type,
            parent_node=parent_node or clean,
            ctx=walk.ctx,
            walk=walk,
            extracted_class_by_widget_name=extracted_class_by_widget_name,
            scroll_content_root=scroll_content_root,
        )

    child_widgets = [
        ir_recurse(
            child,
            parent_type=NodeType.COLUMN if metadata_column_host else clean.type,
            parent_node=clean,
        )
        for child in sorted_children
        if child.id not in paired_circle_ids
        and child.id not in omit_child_ids
        and child.id not in playback_seek_ids
        and child.id not in playback_decor_omit_ids
    ]
    if merged_thumb_widgets:
        child_widgets.extend(merged_thumb_widgets)
    playback_seek_widget = None
    if playback_seek_ids:
        from figma_flutter_agent.generator.layout.widgets.playback import (
            _render_playback_seek_slider,
        )

        playback_seek_widget = _render_playback_seek_slider(clean)
    flow = build_flow_context(
        clean,
        child_widgets=child_widgets,
        sorted_children=sorted_children,
        parent_type=parent_type,
        parent_node=parent_node,
        is_layout_root=is_layout_root,
        scroll_content_root=scroll_content_root,
        metadata_column_host=metadata_column_host,
        paired_circle_ids=paired_circle_ids,
        omit_child_ids=omit_child_ids,
        playback_seek_ids=playback_seek_ids,
        playback_decor_omit_ids=playback_decor_omit_ids,
        playback_seek_widget=playback_seek_widget,
    )
    render_ctx = build_render_ctx(
        uses_svg=bool(kwargs.get("uses_svg")),
        theme_variant=str(kwargs.get("theme_variant", "material_3")),
        cluster_classes=kwargs.get("cluster_classes"),  # type: ignore[arg-type]
        cluster_vector_variants=kwargs.get("cluster_vector_variants"),  # type: ignore[arg-type]
        cluster_vector_variant=kwargs.get("cluster_vector_variant"),
        skip_cluster_id=kwargs.get("skip_cluster_id"),  # type: ignore[arg-type]
        responsive_enabled=bool(kwargs.get("responsive_enabled")),
        design_artboard_width=kwargs.get("design_artboard_width"),  # type: ignore[arg-type]
        bundled_font_families=kwargs.get("bundled_font_families"),  # type: ignore[arg-type]
        dart_weight_overrides_by_family=kwargs.get("dart_weight_overrides_by_family"),  # type: ignore[arg-type]
        text_theme_slot_by_style_name=kwargs.get("text_theme_slot_by_style_name"),  # type: ignore[arg-type]
        text_theme_size_slots=kwargs.get("text_theme_size_slots"),  # type: ignore[arg-type]
        de_archetype_pass=bool(kwargs.get("de_archetype_pass", False)),
    )
    return render_layout_shell(
        clean,
        child_widgets,
        ctx=render_ctx,
        flow=flow,
        recurse=ir_recurse,
    )


def emit_screen_body_from_ir(
    screen_ir: ScreenIr,
    merged_root: CleanDesignTreeNode,
    *,
    ctx: IrEmitContext,
    extracted_class_by_widget_name: dict[str, str] | None = None,
    figma_id_to_widget_name: dict[str, str] | None = None,
) -> str:
    """Emit the screen body by walking merged clean tree with screen IR."""
    ir_by_id = index_ir_tree(screen_ir.root)
    walk = IrEmitWalkState(
        ir_by_id=ir_by_id,
        ctx=ctx,
        extracted_class_by_widget_name=extracted_class_by_widget_name,
        figma_id_to_widget_name=figma_id_to_widget_name,
    )
    root_ir = ir_by_id.get(merged_root.id, screen_ir.root)
    return emit_widget_expression(
        root_ir,
        clean=merged_root,
        parent_type=None,
        ctx=ctx,
        walk=walk,
        extracted_class_by_widget_name=extracted_class_by_widget_name,
    )


def emit_merged_root_expression(
    merged_root: CleanDesignTreeNode,
    *,
    ctx: IrEmitContext,
    screen_ir: ScreenIr | None = None,
    extracted_class_by_widget_name: dict[str, str] | None = None,
) -> str:
    """Emit the root widget expression from a merged clean tree."""
    if screen_ir is not None:
        return emit_screen_body_from_ir(
            screen_ir,
            merged_root,
            ctx=ctx,
            extracted_class_by_widget_name=extracted_class_by_widget_name,
        )
    return render_leaf_body(
        merged_root,
        is_layout_root=ctx.is_layout_root,
        **render_kwargs(ctx),
    )


def emit_extracted_ref(
    ir: WidgetIrNode,
    *,
    extracted_class_by_widget_name: dict[str, str] | None = None,
    figma_id_to_widget_name: dict[str, str] | None = None,
) -> str:
    ref = ir.ref
    if ref is None or not ref.widget_name.strip():
        return "const SizedBox.shrink()"
    widget_name = ref.widget_name.strip()
    if figma_id_to_widget_name:
        widget_name = figma_id_to_widget_name.get(ir.figma_id, widget_name)
    class_name = widget_name
    if extracted_class_by_widget_name:
        class_name = extracted_class_by_widget_name.get(widget_name, class_name)
    else:
        class_name = _canonical_widget_class_name(class_name)
    args = ", ".join(f"{name}: {format_ir_arg(value)}" for name, value in ref.named_args.items())
    if args:
        return f"{class_name}({args})"
    return f"{class_name}()"


def format_ir_arg(value: object) -> str:
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


def apply_ir_wrap(
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
