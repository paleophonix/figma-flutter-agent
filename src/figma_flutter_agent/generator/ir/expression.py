"""Dart expression emission from screen IR nodes."""

from __future__ import annotations

from loguru import logger

from figma_flutter_agent.generator.dart.llm_codegen import _canonical_widget_class_name
from figma_flutter_agent.generator.ir.context import IrEmitContext, render_kwargs
from figma_flutter_agent.generator.ir.semantic_emit import emit_semantic_widget
from figma_flutter_agent.generator.layout import render_node_body
from figma_flutter_agent.generator.layout.flex_policy import (
    FlexWrapKind,
    apply_flex_wrap_to_widget,
    emit_flexible_loose,
)
from figma_flutter_agent.schemas import (
    SEMANTIC_MVP_IR_KINDS,
    STUB_IR_KINDS,
    CleanDesignTreeNode,
    FlexWrapIr,
    NodeType,
    WidgetIrKind,
    WidgetIrNode,
)

_FLEX_WRAP_IR_TO_KIND: dict[FlexWrapIr, FlexWrapKind] = {
    FlexWrapIr.NONE: FlexWrapKind.NONE,
    FlexWrapIr.EXPANDED: FlexWrapKind.EXPANDED,
    FlexWrapIr.FLEXIBLE_LOOSE: FlexWrapKind.FLEXIBLE_LOOSE,
    FlexWrapIr.SIZED_BOX_WIDTH: FlexWrapKind.SIZED_BOX_WIDTH,
}


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
        return emit_extracted_ref(
            ir,
            extracted_class_by_widget_name=extracted_class_by_widget_name,
        )
    if ir.kind in SEMANTIC_MVP_IR_KINDS:
        widget = emit_semantic_widget(ir, clean=clean, ctx=ctx)
        return apply_ir_wrap(widget, ir=ir, parent_type=parent_type, clean=clean)
    if ir.kind in STUB_IR_KINDS:
        logger.warning(
            "Stub IR kind {} for figmaId {}; falling back to layout emit",
            ir.kind.value,
            ir.figma_id,
        )

    widget = render_node_body(
        clean,
        parent_type=parent_type,
        is_layout_root=ctx.is_layout_root and parent_type is None,
        **render_kwargs(ctx),
    )
    return apply_ir_wrap(widget, ir=ir, parent_type=parent_type, clean=clean)


def emit_merged_root_expression(
    merged_root: CleanDesignTreeNode,
    *,
    ctx: IrEmitContext,
) -> str:
    """Emit the root widget expression from a merged clean tree."""
    return render_node_body(
        merged_root,
        is_layout_root=ctx.is_layout_root,
        **render_kwargs(ctx),
    )


def emit_extracted_ref(
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
