"""Jinja2 emission for semantic MVP widget IR kinds."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from figma_flutter_agent.generator.ir.context import IrEmitContext
from figma_flutter_agent.generator.ir.style_context import build_style_context
from figma_flutter_agent.generator.layout.common import escape_dart_string
from figma_flutter_agent.schemas import (
    SEMANTIC_MVP_IR_KINDS,
    CleanDesignTreeNode,
    WidgetIrKind,
    WidgetIrNode,
)

_TEMPLATE_BY_KIND: dict[WidgetIrKind, str] = {
    WidgetIrKind.INPUT_TEXT_FIELD: "widgets/input_text_field.dart.j2",
    WidgetIrKind.BUTTON_FILLED: "widgets/button_filled.dart.j2",
    WidgetIrKind.BUTTON_OUTLINED: "widgets/button_outlined.dart.j2",
    WidgetIrKind.BUTTON_TEXT: "widgets/button_text.dart.j2",
    WidgetIrKind.CHIP_CHOICE: "widgets/chip_choice.dart.j2",
    WidgetIrKind.CONTAINER_CARD: "widgets/container_card.dart.j2",
    WidgetIrKind.CONTAINER_LIST_TILE: "widgets/container_list_tile.dart.j2",
    WidgetIrKind.NAV_SCROLL_HOST: "widgets/nav_scroll_host.dart.j2",
    WidgetIrKind.TECHNICAL_DIVIDER: "widgets/technical_divider.dart.j2",
}


@lru_cache(maxsize=1)
def _template_env() -> Environment:
    base = Path(__file__).resolve().parents[1] / "templates"
    return Environment(
        loader=FileSystemLoader(str(base)),
        autoescape=select_autoescape(default=False),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def _primary_text(clean: CleanDesignTreeNode, ir: WidgetIrNode) -> str:
    if ir.overrides is not None and ir.overrides.text:
        return ir.overrides.text
    if clean.text:
        return clean.text
    for child in clean.children:
        if child.text:
            return child.text
    return ""


def _build_template_context(
    ir: WidgetIrNode,
    clean: CleanDesignTreeNode,
    ctx: IrEmitContext,
) -> dict[str, object]:
    def dart_literal(value: str) -> str:
        return f"'{escape_dart_string(value)}'"

    label = _primary_text(clean, ir)
    style = build_style_context(clean, ctx=ctx).as_template_dict()
    context: dict[str, object] = {
        "theme_variant": ctx.theme_variant,
        "label": dart_literal(label),
        "is_selected": ir.is_selected if ir.is_selected is not None else False,
        "hint_text": dart_literal(ir.hint_text or ""),
        "error_text": dart_literal(ir.error_text or ""),
        "is_multiline": bool(ir.is_multiline),
        "max_lines": ir.max_lines if ir.max_lines is not None else 1,
        "flex_spacing": (
            ir.layout_hints.flex_spacing
            if ir.layout_hints is not None and ir.layout_hints.flex_spacing is not None
            else clean.spacing
        ),
        "style": style,
    }
    if ir.payload is not None:
        payload_dump = ir.payload.model_dump(by_alias=False, exclude_none=True)
        context["payload"] = payload_dump
    return context


def emit_semantic_widget(
    ir: WidgetIrNode,
    *,
    clean: CleanDesignTreeNode,
    ctx: IrEmitContext,
    child_expression: str | None = None,
) -> str:
    """Render a semantic widget Dart expression from IR and clean-tree context.

    Args:
        ir: Semantic IR node.
        clean: Matching clean-tree node.
        ctx: Shared emit context.
        child_expression: Optional pre-rendered child for host widgets.

    Returns:
        Dart widget expression string.
    """
    if ir.kind not in SEMANTIC_MVP_IR_KINDS:
        msg = f"emit_semantic_widget called for non-MVP kind {ir.kind!r}"
        raise ValueError(msg)
    template_name = _TEMPLATE_BY_KIND[ir.kind]
    template_ctx = _build_template_context(ir, clean, ctx)
    if child_expression is not None:
        template_ctx["child"] = child_expression
    return _template_env().get_template(template_name).render(**template_ctx).strip()


__all__ = ["SEMANTIC_MVP_IR_KINDS", "emit_semantic_widget"]
